from smbconnect.config import AppConfig, ServerProfile, load_config, save_config


def test_roundtrip(tmp_path):
    path = tmp_path / "profiles.json"
    cfg = AppConfig(servers=[ServerProfile(name="NAS", host="nas", share="data", username="NAS\\jan", drive="Z:")])
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.servers[0].host == "nas"
    assert loaded.servers[0].unc == "\\\\nas\\data"
    assert "password" not in path.read_text()


def test_missing_and_corrupt(tmp_path):
    path = tmp_path / "profiles.json"
    assert load_config(path).servers == []
    path.write_text("{kapot")
    assert load_config(path).servers == []
    assert (tmp_path / "profiles.corrupt.json").exists()


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text('{"servers":[{"host":"pc1","nieuw":1}],"settings":{"x":1}}')
    assert load_config(path).servers[0].host == "pc1"
