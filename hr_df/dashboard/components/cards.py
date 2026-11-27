"""설명 카드: 요약 박스, 목록 카드, 인사이트 카드. 모든 문자열은 escape한다."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape


def _items(items: Sequence[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def callout(title: str, items: Sequence[str]) -> str:
    """핵심 요약. 옅은 배경과 왼쪽 선으로 본문과 구분한다."""
    return (
        f'<aside class="hr-callout"><strong>{escape(title)}</strong>'
        f"<ul>{_items(items)}</ul></aside>"
    )


def text_card(title: str, items: Sequence[str], *, tone: str = "neutral") -> str:
    return (
        f'<section class="hr-text-card hr-text-card--{escape(tone)}">'
        f"<h4>{escape(title)}</h4><ul>{_items(items)}</ul></section>"
    )


def text_grid(cards: Sequence[str]) -> str:
    return f'<div class="hr-text-grid">{"".join(cards)}</div>'


@dataclass(frozen=True)
class Insight:
    """HR Insights 화면의 인사이트 한 개."""

    key: str
    tag: str
    title: str
    finding: str  # 분석 결과(한 문장)
    interpretation: Sequence[str]
    actions: Sequence[str]
    limits: Sequence[str]
    small_groups: Sequence[str] = field(default_factory=tuple)


def insight_header(insight: Insight) -> str:
    flag = ""
    if insight.small_groups:
        names = ", ".join(insight.small_groups)
        flag = (
            f'<p class="hr-flag">※ 30명 미만 소집단 포함: {escape(names)}. '
            "비율이 크게 흔들릴 수 있습니다.</p>"
        )
    return (
        f'<div class="hr-insight-head"><span class="hr-tag">{escape(insight.tag)}</span>'
        f"<h3>{escape(insight.title)}</h3>"
        f'<p class="hr-finding"><span>분석 결과</span>{escape(insight.finding)}</p>{flag}</div>'
    )


def insight_body(insight: Insight) -> str:
    return text_grid(
        [
            text_card("해석", insight.interpretation),
            text_card("실무 개선 제안", insight.actions, tone="action"),
            text_card("분석의 한계", insight.limits, tone="limit"),
        ]
    )
