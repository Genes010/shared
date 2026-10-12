import base64

from smbconnect.runner import as_list, clean_clixml, encode_ps, parse_json_output, ps_quote


def test_ps_quote_escapes_single_quotes():
    assert ps_quote("O'Brien") == "'O''Brien'"


def test_encode_ps_roundtrip():
    s = "Write-Output 'héllo'"
    assert base64.b64decode(encode_ps(s)).decode("utf-16-le") == s


def test_parse_json_output_with_noise():
    assert parse_json_output('WARNING: x\n{"a":1}\n') == {"a": 1}
    assert parse_json_output("true") is True
    assert parse_json_output("") is None


def test_as_list():
    assert as_list(None) == []
    assert as_list({"a": 1}) == [{"a": 1}]
    assert as_list([1, 2]) == [1, 2]


def test_clean_clixml():
    raw = '#< CLIXML\r\n<Objs Version="1.1.0.1"><S S="Error">Toegang geweigerd_x000D__x000A_</S></Objs>'
    assert clean_clixml(raw) == "Toegang geweigerd"
    assert clean_clixml("gewone tekst") == "gewone tekst"
