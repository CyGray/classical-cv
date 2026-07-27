#!/usr/bin/env python
"""Render a Markdown document to PDF.

Supports the subset used by the docs in this repo: ATX headings, paragraphs,
bullet/ordered lists, GFM pipe tables, blockquotes, horizontal rules, and
inline bold/italic/code.

Usage:
    python scripts/md_to_pdf.py docs/PAPER_WRITING_GUIDE.md docs/PAPER_WRITING_GUIDE.pdf
"""

from __future__ import annotations

import re
import sys
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

MARGIN = 0.85 * inch
PAGE_W, PAGE_H = LETTER
BODY_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5b5b5b")
RULE = colors.HexColor("#c8c8c8")
BAND = colors.HexColor("#f0f0f0")
ACCENT = colors.HexColor("#8a1c1c")


def styles():
    ss = getSampleStyleSheet()
    base = dict(fontName="Helvetica", textColor=INK, leading=13.6, fontSize=9.6)
    s = {
        "body": ParagraphStyle("body", ss["Normal"], spaceAfter=7, alignment=TA_LEFT, **base),
        "h1": ParagraphStyle(
            "h1", ss["Normal"], fontName="Helvetica-Bold", fontSize=19, leading=23,
            textColor=INK, spaceBefore=4, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", ss["Normal"], fontName="Helvetica-Bold", fontSize=13.5, leading=17,
            textColor=ACCENT, spaceBefore=17, spaceAfter=7,
        ),
        "h3": ParagraphStyle(
            "h3", ss["Normal"], fontName="Helvetica-Bold", fontSize=10.8, leading=14,
            textColor=INK, spaceBefore=12, spaceAfter=5,
        ),
        "quote": ParagraphStyle(
            "quote", ss["Normal"], fontName="Helvetica-Oblique", fontSize=9.4, leading=13.4,
            textColor=MUTED, leftIndent=16, rightIndent=10, spaceBefore=4, spaceAfter=9,
            borderPadding=0,
        ),
        "cell": ParagraphStyle("cell", ss["Normal"], fontSize=8.2, leading=10.4, textColor=INK,
                               fontName="Helvetica"),
        "cellh": ParagraphStyle("cellh", ss["Normal"], fontSize=8.2, leading=10.4, textColor=INK,
                                fontName="Helvetica-Bold"),
    }
    s["li"] = ParagraphStyle("li", s["body"], leftIndent=15, bulletIndent=4, spaceAfter=3.5)
    return s


def inline(text: str) -> str:
    """Markdown inline formatting -> reportlab mini-HTML.

    Code spans are held aside while emphasis is applied, so that `*` and `_`
    inside a path or glob are not read as markup.
    """
    out = escape(text, quote=False)

    spans: list[str] = []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    out = re.sub(r"`([^`]+)`", stash, out)
    out = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<i>\1</i>", out)

    def restore(m):
        return f'<font face="Courier" size="8.6">{spans[int(m.group(1))]}</font>'

    return re.sub(r"\x00(\d+)\x00", restore, out)


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_sep(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|[\s:|-]*", line.strip())) and "-" in line


def aligns(sep: str) -> list[str]:
    out = []
    for c in split_row(sep):
        if c.endswith(":") and c.startswith(":"):
            out.append("CENTER")
        elif c.endswith(":"):
            out.append("RIGHT")
        else:
            out.append("LEFT")
    return out


def build_table(rows: list[list[str]], align: list[str], st) -> Table:
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    align = (align + ["LEFT"] * ncols)[:ncols]

    data = [[Paragraph(inline(c), st["cellh"]) for c in rows[0]]]
    for r in rows[1:]:
        data.append([Paragraph(inline(c), st["cell"]) for c in r])

    # Width proportional to the longest raw cell per column, clamped so no
    # column starves.
    weights = []
    for i in range(ncols):
        longest = max(len(r[i]) for r in rows)
        weights.append(max(4.0, min(float(longest), 46.0)))
    total = sum(weights)
    widths = [BODY_W * w / total for w in weights]

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
    ]
    for i, a in enumerate(align):
        style.append(("ALIGN", (i, 0), (i, -1), a))
    t.setStyle(TableStyle(style))
    return t


def parse(md: str, st) -> list:
    flow = []
    lines = md.split("\n")
    i = 0
    para: list[str] = []

    def flush():
        nonlocal para
        if para:
            flow.append(Paragraph(inline(" ".join(para)), st["body"]))
            para = []

    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()

        if not stripped:
            flush()
            i += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            flush()
            flow.append(Spacer(1, 5))
            flow.append(HRFlowable(width="100%", thickness=0.7, color=RULE))
            flow.append(Spacer(1, 5))
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush()
            lvl = min(len(m.group(1)), 3)
            flow.append(Paragraph(inline(m.group(2)), st[f"h{lvl}"]))
            i += 1
            continue

        # GFM table
        if stripped.startswith("|") and i + 1 < len(lines) and is_sep(lines[i + 1]):
            flush()
            header = split_row(stripped)
            align = aligns(lines[i + 1])
            body = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(split_row(lines[i]))
                i += 1
            flow.append(Spacer(1, 3))
            flow.append(build_table([header] + body, align, st))
            flow.append(Spacer(1, 9))
            continue

        if stripped.startswith(">"):
            flush()
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip().lstrip(">").strip())
                i += 1
            text = " ".join(x for x in block if x)
            flow.append(Paragraph(inline(text), st["quote"]))
            continue

        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", ln)
        if m:
            flush()
            indent, marker, text = m.group(1), m.group(2), m.group(3)
            # absorb continuation lines
            i += 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i])
                and not lines[i].strip().startswith(("#", "|", ">"))
                and lines[i].startswith(" ")
            ):
                text += " " + lines[i].strip()
                i += 1
            bullet = marker if marker[0].isdigit() else "•"
            sty = ParagraphStyle(
                "lix", st["li"], leftIndent=15 + 14 * (len(indent) // 2),
                bulletIndent=4 + 14 * (len(indent) // 2),
            )
            flow.append(Paragraph(inline(text), sty, bulletText=bullet))
            continue

        para.append(stripped)
        i += 1

    flush()
    return flow


def render(src: str, dst: str, title: str) -> None:
    st = styles()
    md = open(src, encoding="utf-8").read()

    doc = BaseDocTemplate(
        dst, pagesize=LETTER,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN + 6,
        title=title, author="Group 3, University of St. La Salle",
    )
    frame = Frame(MARGIN, MARGIN, BODY_W, PAGE_H - 2 * MARGIN - 8, id="body")

    def decorate(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, MARGIN - 16, title)
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 16, str(canvas.getPageNumber()))
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, MARGIN - 8, PAGE_W - MARGIN, MARGIN - 8)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])

    story = parse(md, st)
    # Keep each heading with the block that follows it.
    glued = []
    n = len(story)
    for idx, f in enumerate(story):
        if (
            isinstance(f, Paragraph)
            and f.style.name in ("h2", "h3")
            and idx + 1 < n
            and not isinstance(story[idx + 1], (Table, KeepTogether))
        ):
            glued.append(KeepTogether([f, story[idx + 1]]))
            story[idx + 1] = Spacer(0, 0)
        else:
            glued.append(f)
    doc.build(glued)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    out_title = sys.argv[3] if len(sys.argv) > 3 else "LS-Face: Paper Writing Guide"
    render(sys.argv[1], sys.argv[2], out_title)
    print(f"wrote {sys.argv[2]}")
