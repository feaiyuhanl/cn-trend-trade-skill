from __future__ import annotations

from core.assemble import assemble
from core.validate import load_json, validate_market_pack


def test_assemble_applies_consultation_slot(tmp_path, monkeypatch):
    from core import assemble as asm

    monkeypatch.setattr(asm, "TMP_DIR", tmp_path)
    monkeypatch.setattr(asm, "OUT_PACK", tmp_path / "market_pack.json")
    path = assemble(symbols=["600519.SH"], session_mode="new_entry")
    pack = load_json(path)
    assert "slots" in pack
    assert "consultation" in pack["slots"]
    assert pack["slots"]["consultation"]["meta"]["adapter_id"] == "consultation_stub"
    assert validate_market_pack(pack) == []
