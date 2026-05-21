from __future__ import annotations

from core.review_brief import build_review_brief


def test_review_brief_renders_sections() -> None:
    text = build_review_brief(days=5)
    assert "复盘简报" in text
    assert "机检规则提醒" in text
    assert "SKILL 八维演进评估" in text
    assert "MF_PHASE_ENTRY" in text


def test_review_brief_holdings_focus() -> None:
    text = build_review_brief(focus="holdings", days=3)
    assert "持仓快照" in text
    assert "历史推荐记录" not in text
