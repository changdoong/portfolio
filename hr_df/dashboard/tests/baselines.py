"""보고서와 Notebook 저장 출력에서 기대 수치를 읽는다. Notebook은 실행하지 않는다."""

import json
import re
from functools import cache
from html.parser import HTMLParser
from typing import NamedTuple

from core import config


class Table(NamedTuple):
    header: list[str]
    rows: list[list[str]]


@cache
def report_text() -> str:
    path = config.PROJECT_ROOT / "reports" / "HR_Analytics_final_report.md"
    return path.read_text(encoding="utf-8")


@cache
def report_tables() -> tuple[Table, ...]:
    tables = []
    for block in re.findall(r"(?:^\|.*(?:\n|$))+", report_text(), re.MULTILINE):
        rows = [
            [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
            for line in block.strip().splitlines()
        ]
        tables.append(Table(rows[0], rows[2:]))  # 두 번째 줄은 구분선
    return tuple(tables)


def report_table(*header: str) -> Table:
    matches = [table for table in report_tables() if table.header == list(header)]
    assert len(matches) == 1, f"보고서 표를 특정할 수 없음: {header}"
    return matches[0]


@cache
def notebook_outputs(prefix: str) -> tuple[dict, ...]:
    paths = [
        path
        for path in (config.PROJECT_ROOT / "notebooks").glob("*.ipynb")
        if path.name.strip().startswith(prefix)
    ]
    assert len(paths) == 1, f"Notebook을 특정할 수 없음: {prefix}"
    cells = json.loads(paths[0].read_text(encoding="utf-8"))["cells"]
    return tuple(output for cell in cells for output in cell.get("outputs", []))


def notebook_text(prefix: str) -> str:
    parts = []
    for output in notebook_outputs(prefix):
        parts.extend(output.get("text", []))
        parts.extend(output.get("data", {}).get("text/plain", []))
        parts.append("\n")
    return "".join(parts)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self._cell: list[str] | None = None
        self._row: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td"):
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None:
            text = "".join(self._cell).strip()
            (self.headers if tag == "th" else self._row).append(text)
            self._cell = None
        elif tag == "tr" and self._row:
            self.rows.append(self._row)


@cache
def notebook_tables(prefix: str) -> tuple[Table, ...]:
    tables = []
    for output in notebook_outputs(prefix):
        if html := "".join(output.get("data", {}).get("text/html", [])):
            parser = _TableParser()
            parser.feed(html)
            if parser.rows:
                tables.append(Table([cell for cell in parser.headers if cell], parser.rows))
    return tuple(tables)


def assert_displayed(actual: float, displayed: str) -> None:
    """문서에 표시된 자릿수까지 일치하는지 확인한다."""
    text = displayed.replace(",", "").rstrip("%명개건")
    decimals = len(text.partition(".")[2])
    assert f"{actual:.{decimals}f}" == text, f"계산값 {actual} != 문서값 {displayed}"
