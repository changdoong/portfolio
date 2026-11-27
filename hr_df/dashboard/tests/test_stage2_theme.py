"""작업 1: 디자인 시스템."""

import re
import tomllib

import pytest

from components import theme
from core import config

SETTINGS = tomllib.loads(
    (config.PROJECT_ROOT / "dashboard" / ".streamlit" / "config.toml").read_text(encoding="utf-8")
)


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    red, green, blue = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


@pytest.mark.parametrize(
    "foreground,background,minimum",
    [
        ("ink", "surface", 4.5),
        ("ink", "page", 4.5),
        ("ink-muted", "surface", 4.5),
        ("ink-muted", "page", 4.5),
        ("on-navy", "navy", 4.5),
        ("on-navy", "navy-raised", 4.5),
        ("on-navy-muted", "navy", 4.5),
        ("retained", "surface", 3.0),
        ("attrition", "surface", 3.0),
    ],
)
def test_contrast(foreground, background, minimum):
    low, high = sorted([_luminance(theme.COLORS[name]) for name in (foreground, background)])
    assert (high + 0.05) / (low + 0.05) >= minimum


def test_config_matches_tokens():
    main, sidebar = SETTINGS["theme"], SETTINGS["theme"]["sidebar"]
    assert main["primaryColor"] == theme.COLORS["navy"]
    assert main["backgroundColor"] == theme.COLORS["page"]
    assert main["secondaryBackgroundColor"] == theme.COLORS["surface"]
    assert main["textColor"] == theme.COLORS["ink"]
    assert main["borderColor"] == theme.COLORS["border"]
    assert main["font"] == theme.FONT_FAMILY
    assert sidebar["backgroundColor"] == theme.COLORS["navy"]
    assert sidebar["textColor"] == theme.COLORS["on-navy"]


def test_server_is_private():
    assert SETTINGS["server"]["address"] == "127.0.0.1"
    assert SETTINGS["browser"]["gatherUsageStats"] is False
    assert SETTINGS["client"]["showErrorDetails"] == "type"


def test_css_uses_only_defined_tokens():
    source = theme.CSS_PATH.read_text(encoding="utf-8")
    assert set(re.findall(r"var\(--([\w-]+)\)", source)) <= set(theme.COLORS)
    assert not re.search(r"#[0-9a-fA-F]{6}\b", source), "CSS에 색상을 직접 쓰지 않는다."


def test_css_loads_nothing_external():
    css = theme.build_css()
    assert "http" not in css
    assert "@import" not in css


def test_secrets_are_ignored():
    path = config.PROJECT_ROOT / "dashboard" / ".streamlit" / ".gitignore"
    assert "secrets.toml" in path.read_text(encoding="utf-8").splitlines()
