"""
views/widgets/code_highlighter.py
---------------------------------
Lightweight multi-language ``QSyntaxHighlighter`` for the Table page's code
preview.

Highlights keywords, numbers, strings and comments for a small set of language
tags (``python`` | ``c`` | ``matlab``) emitted by ``models/data_export.py``.
Colors come from the PALETTE singleton — no hex literals appear here.
"""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)

from wizard_4155_4156.styles.theme import PALETTE as P

_KEYWORDS: dict[str, list[str]] = {
    "python": [
        "import",
        "from",
        "as",
        "def",
        "return",
        "for",
        "in",
        "if",
        "else",
        "elif",
        "while",
        "True",
        "False",
        "None",
    ],
    "c": [
        "double",
        "int",
        "float",
        "char",
        "void",
        "const",
        "static",
        "define",
        "include",
        "return",
        "for",
        "while",
        "if",
        "else",
    ],
    "matlab": [
        "function",
        "end",
        "for",
        "while",
        "if",
        "else",
        "elseif",
        "return",
        "NaN",
        "Inf",
    ],
}

_COMMENTS: dict[str, list[str]] = {
    "python": [r"#[^\n]*"],
    "matlab": [r"%[^\n]*"],
    "c": [r"//[^\n]*", r"/\*.*\*/"],
}

_NUMBER = r"\b\d[\d.]*(?:[eE][+-]?\d+)?\b"
_STRINGS = [r"\"[^\"]*\"", r"'[^']*'"]


def _fmt(
    color: str, *, bold: bool = False, italic: bool = False
) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class CodeHighlighter(QSyntaxHighlighter):
    """Re-targetable rule-based highlighter for several languages."""

    def __init__(
        self, document: QTextDocument, language: str | None = None
    ) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self.set_language(language)

    def set_language(self, language: str | None) -> None:
        """Rebuild the rules for *language* and re-highlight the document."""
        self._rules = self._build_rules(language)
        self.rehighlight()

    @staticmethod
    def _build_rules(
        language: str | None,
    ) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        if not language:
            return []
        kw_fmt = _fmt(P.ACCENT_HOVER, bold=True)
        num_fmt = _fmt(P.STATUS_WARN)
        str_fmt = _fmt(P.STATUS_OK)
        com_fmt = _fmt(P.TEXT_MUTED, italic=True)

        rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(_NUMBER), num_fmt)
        ]
        for kw in _KEYWORDS.get(language, []):
            rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))
        for pattern in _STRINGS:
            rules.append((QRegularExpression(pattern), str_fmt))
        # Comments are added last so they override any earlier match.
        for pattern in _COMMENTS.get(language, []):
            rules.append((QRegularExpression(pattern), com_fmt))
        return rules

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        for regex, fmt in self._rules:
            matches = regex.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(
                    match.capturedStart(), match.capturedLength(), fmt
                )
