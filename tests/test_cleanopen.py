from er_kit import cleanopen


def _touch(tmp_path, name):
    """clean_open fails fast on missing paths, so mocked tests need a real file."""
    p = tmp_path / name
    p.write_bytes(b"stub")
    return str(p)


def test_path_passed_as_argv_not_interpolated(monkeypatch, tmp_path):
    # regression: the path must be an osascript ARGV item, never interpolated into the
    # AppleScript text (a path with a quote would otherwise break/inject the script).
    captured = {}

    class _R:
        returncode = 0
        stdout = 'CLEAN OPEN OK | workbook=a" ; do shell script "evil".xlsx | sheets=1'
        stderr = ""

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return _R()

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", fake_run)
    bad = _touch(tmp_path, 'a" ; do shell script "evil".xlsx')
    ok, msg = cleanopen.clean_open(bad, delay=0.1)
    assert ok
    cmd = captured["cmd"]
    assert bad in cmd  # passed as its own argv element
    script = cmd[cmd.index("-e") + 1]
    assert bad not in script  # NOT embedded in the script text
    assert "on run argv" in script
    assert "close targetBook saving no" in script
    assert "close active workbook" not in script
    assert "active workbook" not in script  # resolution is by expected name, never by focus


def test_timeout_passed_to_osascript(monkeypatch, tmp_path):
    captured = {}

    class _R:
        returncode = 0
        stdout = "CLEAN OPEN OK | workbook=x.xlsx | sheets=1"
        stderr = ""

    def fake_run(cmd, **kw):
        captured.update(kw)
        return _R()

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", fake_run)
    ok, _ = cleanopen.clean_open(_touch(tmp_path, "x.xlsx"), delay=0.1, timeout=7)

    assert ok
    assert captured["timeout"] == 7


def test_returns_false_when_excel_reports_different_workbook(monkeypatch, tmp_path):
    class _R:
        returncode = 0
        stdout = "CLEAN OPEN OK | workbook=Book1 | sheets=1"
        stderr = ""

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())

    ok, msg = cleanopen.clean_open(_touch(tmp_path, "target.xlsx"), delay=0.1)

    assert ok is False
    assert "expected='target.xlsx'" in msg
    assert "actual='Book1'" in msg


def test_returns_false_when_workbook_unresolvable(monkeypatch, tmp_path):
    # The AppleScript reports ABSENT when the opened file never registers by name
    # (silent open failure, or a modal blocking opens) — the gate must fail.
    class _R:
        returncode = 0
        stdout = "CLEAN OPEN OK | workbook=ABSENT | sheets=0"
        stderr = ""

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())

    ok, msg = cleanopen.clean_open(_touch(tmp_path, "target.xlsx"), delay=0.1)

    assert ok is False
    assert "actual='ABSENT'" in msg


def test_accepts_matching_workbook_name_with_or_without_extension(monkeypatch, tmp_path):
    class _R:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")

    for workbook_name in ("Target.xlsx", "target"):
        _R.stdout = f"CLEAN OPEN OK | workbook={workbook_name} | sheets=1"
        monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())

        ok, _ = cleanopen.clean_open(_touch(tmp_path, "target.xlsx"), delay=0.1)

        assert ok is True


def test_non_macos_skips(monkeypatch):
    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Linux")
    ok, msg = cleanopen.clean_open("/tmp/x.xlsx")
    assert ok and "skipped" in msg


def test_returns_false_on_repair_or_error(monkeypatch, tmp_path):
    class _R:
        returncode = 1
        stdout = ""
        stderr = "could not open: file is corrupt"

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())
    ok, msg = cleanopen.clean_open(_touch(tmp_path, "x.xlsx"), delay=0.1)
    assert ok is False
    assert "repair-dialog/workbook failure" in msg
    assert "corrupt" in msg


def test_environment_failure_message_distinguishes_osascript_error(monkeypatch, tmp_path):
    class _R:
        returncode = 1
        stdout = ""
        stderr = "execution error: Microsoft Excel got an error: Parameter error. (-50)"

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())
    ok, msg = cleanopen.clean_open(_touch(tmp_path, "x.xlsx"), delay=0.1)
    assert ok is False
    assert msg.startswith("environment/automation failure:")
    assert "-50" in msg


def test_environment_failure_message_distinguishes_no_active_workbook(monkeypatch, tmp_path):
    class _R:
        returncode = 1
        stdout = ""
        stderr = "execution error: Microsoft Excel got an error: Can't get active workbook."

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())
    ok, msg = cleanopen.clean_open(_touch(tmp_path, "x.xlsx"), delay=0.1)
    assert ok is False
    assert msg.startswith("environment/automation failure:")
    assert "active workbook" in msg


def test_environment_failure_message_distinguishes_unavailable_automation(monkeypatch, tmp_path):
    class _R:
        returncode = 1
        stdout = ""
        stderr = "Connection Invalid error for service com.apple.hiservices-xpcservice."

    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cleanopen.subprocess, "run", lambda cmd, **kw: _R())
    ok, msg = cleanopen.clean_open(_touch(tmp_path, "x.xlsx"), delay=0.1)
    assert ok is False
    assert msg.startswith("environment/automation failure:")


def test_missing_file_fails_without_touching_excel(monkeypatch):
    # A missing path must fail BEFORE osascript runs: handing Excel a missing file pops a
    # modal "couldn't find" alert that blocks every later programmatic open (observed live
    # 2026-07-25 — it wedged the gate for all subsequent files until manually dismissed).
    monkeypatch.setattr(cleanopen.platform, "system", lambda: "Darwin")

    def boom(*a, **kw):
        raise AssertionError("subprocess.run must not be called for a missing file")

    monkeypatch.setattr(cleanopen.subprocess, "run", boom)
    ok, msg = cleanopen.clean_open("/nonexistent/dir/nope.xlsx", delay=0.1)
    assert not ok
    assert "does not exist" in msg
