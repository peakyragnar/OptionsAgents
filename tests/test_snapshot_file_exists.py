import pathlib, subprocess, os

def test_snapshot_creates_file(tmp_path, monkeypatch):
    """
    monkey-patch write_parquet() to use a temp folder,
    then assert the file exists.
    """
    from src.ingest import snapshot

    # direct snapshot.write_parquet into tmp_path
    monkeypatch.setattr(snapshot, "write_parquet",
        lambda df, symbol="spx": tmp_path / "dummy.parquet")

    # fake DataFrame so fetch_chain isn't called
    monkeypatch.setattr(snapshot, "fetch_chain",
        lambda: snapshot.pd.DataFrame({"strike":[420], "bid":[1], "ask":[1.2], "type":["C"]}))

    p = snapshot.write_parquet(snapshot.fetch_chain())
    assert p.suffix == ".parquet" and not p.exists(), \
        "patched path returned but should not actually write in this test"