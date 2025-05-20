import importlib, pathlib, pytest, os
from typer.testing import CliRunner

@pytest.mark.integration
def test_persistence_creates_db(tmp_path, monkeypatch):
    dbfile = tmp_path / "test.db"
    monkeypatch.setenv("OA_GAMMA_DB", str(dbfile))

    # import triggers DB creation inside persistence
    importlib.import_module("src.persistence")

    # verify the file now exists
    assert dbfile.exists()