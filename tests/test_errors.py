from smbconnect.errors import explain, extract_error_code


def test_net_use_english():
    assert extract_error_code("System error 1326 has occurred.\n\nThe user name or password is incorrect.") == 1326


def test_net_use_dutch():
    assert extract_error_code("Systeemfout 1272 is opgetreden.") == 1272


def test_powershell_error_id():
    assert extract_error_code("New-SmbMapping : ...", "Windows System Error 1219,New-SmbMapping") == 1219


def test_hresult():
    assert extract_error_code("HRESULT 0x80070035") == 53


def test_text_fallback():
    assert extract_error_code("The network name cannot be found.") == 67
    assert extract_error_code("De gebruikersnaam of het wachtwoord is onjuist.") == 1326


def test_unknown():
    assert extract_error_code("niets bruikbaars") is None
    assert extract_error_code(None, "") is None


def test_required_codes_have_explanations():
    for code in (1326, 1272, 53, 67, 1219, 5):
        e = explain(code)
        assert e and e.title and e.explanation and e.fix
