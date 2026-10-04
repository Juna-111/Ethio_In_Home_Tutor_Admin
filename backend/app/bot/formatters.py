import html
from typing import Any


def _format_subjects(subjects: Any) -> str:
    if isinstance(subjects, list):
        return ", ".join(html.escape(str(s)) for s in subjects)
    return html.escape(str(subjects or ""))


def _format_schedule(schedule: Any) -> str:
    if isinstance(schedule, list):
        return ", ".join(html.escape(str(s)) for s in schedule)
    return html.escape(str(schedule or ""))


def _replace_card_header(text: str, new_header_html: str) -> str:
    """Replace the top line of a card while preserving the remaining content."""
    lines = text.split("\n")
    if not lines:
        return new_header_html
    remaining_lines = [html.escape(line) for line in lines[1:]]
    return new_header_html + "\n" + "\n".join(remaining_lines)
