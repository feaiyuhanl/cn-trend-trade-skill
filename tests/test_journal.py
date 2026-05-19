from core.journal import list_journal_dates, load_journal, save_journal


def test_save_and_load_journal(tmp_path, monkeypatch):
    import core.journal as jmod

    monkeypatch.setattr(jmod, "JOURNAL_DIR", tmp_path)
    save_journal({"ts_code": "600519.SH", "action": "buy"}, date="20260519")
    assert load_journal("20260519")[0]["ts_code"] == "600519.SH"
    assert "20260519" in list_journal_dates()
