from smbconnect import diagnose as dg
from tests.fakes import FakeRunner

CLIENT = ("Get-SmbClientConfiguration", {"RequireSecuritySignature": True, "EnableSecuritySignature": True,
                                         "EnableInsecureGuestLogons": False, "PolicyAllowInsecureGuestAuth": None,
                                         "PasswordLess": 0})


def run(responses, **params):
    runner = FakeRunner(responses + [CLIENT])
    p = dg.DiagnoseParams(**params)
    return {r.key: r for r in dg.run_diagnosis(runner, p)}, runner


def test_all_green():
    res, runner = run([
        ("GetHostAddresses", {"ok": True, "ips": ["192.168.1.20", "fe80::1"]}),
        ("Test-NetConnection", {"tcp": True, "ping": True, "remote": "192.168.1.20"}),
        ("New-SmbMapping", {"ok": True, "created": True, "conn": {"dialect": "3.1.1", "signed": True}}),
    ], host="pc-zolder", share="Data", username="PC-ZOLDER\\jan", password="geheim")
    assert [res[k].status for k, _ in dg.STEPS] == ["ok", "ok", "ok", "ok", "ok", "ok", "info"]
    # wachtwoord gaat via omgevingsvariabele, niet via het script
    script, kwargs = next(c for c in runner.calls if "New-SmbMapping" in c[0])
    assert "geheim" not in script
    assert kwargs["env"]["SMBC_PASS"] == "geheim"


def test_wrong_password_1326():
    res, _ = run([
        ("GetHostAddresses", {"ok": True, "ips": ["192.168.1.20"]}),
        ("Test-NetConnection", {"tcp": True, "ping": False}),
        ("New-SmbMapping", {"ok": False, "error": "The user name or password is incorrect.",
                            "errorId": "Windows System Error 1326,New-SmbMapping"}),
    ], host="pc", share="d", username="MicrosoftAccount\\a@b.nl", password="x")
    assert res["ping"].status == "warn"  # ICMP geblokkeerd maar SMB open
    assert res["auth"].status == "fail" and "1326" in res["auth"].summary
    assert res["dialect"].status == "skip"
    assert res["account"].status == "warn" and "PIN" in res["account"].summary


def test_guest_blocked_1272():
    res, _ = run([
        ("GetHostAddresses", {"ok": True, "ips": ["10.0.0.5"]}),
        ("Test-NetConnection", {"tcp": True, "ping": True}),
        ("New-SmbMapping", {"ok": False, "error": "x", "errorId": "Windows System Error 1272,New-SmbMapping"}),
    ], host="nas", share="public")
    assert res["auth"].summary.startswith("Fout 1272")
    assert res["client"].status == "warn"


def test_name_fails_falls_back_to_ip():
    res, runner = run([
        ("GetHostAddresses", {"ok": False, "error": "No such host is known"}),
        ("Test-NetConnection", {"tcp": True, "ping": True}),
        ("New-SmbMapping", {"ok": True, "existing": True, "conn": {"dialect": "3.0.2"}}),
    ], host="pc-zolder", ip_fallback="192.168.1.20", share="Data")
    assert res["resolve"].status == "warn"
    tnc = next(c[0] for c in runner.calls if "Test-NetConnection" in c[0])
    assert "'192.168.1.20'" in tnc
    assert res["auth"].status == "ok"


def test_unreachable_skips_rest():
    res, _ = run([
        ("GetHostAddresses", {"ok": True, "ips": ["192.168.1.99"]}),
        ("Test-NetConnection", {"tcp": False, "ping": False}),
    ], host="weg")
    assert res["ping"].status == "fail" and res["port"].status == "fail"
    assert res["auth"].status == "skip" and res["dialect"].status == "skip"


def test_ip_host_and_unc_input():
    assert dg.normalize_host("\\\\pc1\\share") == "pc1"
    res, _ = run([("Test-NetConnection", {"tcp": False, "ping": True})], host="192.168.1.5")
    assert res["resolve"].status == "ok"
    assert res["port"].status == "fail"


def test_old_dialect_warns():
    st = dg.DiagnoseState(auth_ok=True, connection={"dialect": "2.1"})
    assert dg.check_dialect(st).status == "warn"


def test_report_format():
    res, _ = run([("Test-NetConnection", {"tcp": False, "ping": False})], host="1.2.3.4", share="x")
    text = dg.format_report(dg.DiagnoseParams(host="1.2.3.4", share="x"), list(res.values()))
    assert "[FOUT]" in text and "Poort 445" in text
