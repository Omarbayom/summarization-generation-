from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .text_utils import REQUIRED_SECTIONS, esc, parse_sections_from_text


def _styles():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "May26Title",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=15.5,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=12,
        ),
        "team": ParagraphStyle(
            "May26Team",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=10.8,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceBefore=8,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "heading": ParagraphStyle(
            "May26Heading",
            parent=base["Heading3"],
            fontName="Times-Bold",
            fontSize=10.3,
            leading=12.2,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceBefore=6,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "May26Body",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9.3,
            leading=11.2,
            alignment=TA_LEFT,
            textColor=colors.black,
            leftIndent=10,
            firstLineIndent=-10,
            spaceAfter=2.1,
            splitLongWords=True,
        ),
    }


def export_summary_pdf(
    df: pd.DataFrame,
    text_col: str,
    output_pdf: str | Path,
    report_title: str,
    one_team_per_page: bool = False,
) -> str:
    """Export May26-style PDF: continuous team flow, Times font, no raw markdown."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=42,
        bottomMargin=34,
        title=report_title,
    )

    story: list[Any] = []
    story.append(Paragraph(esc(report_title), styles["title"]))

    for idx, row in df.reset_index(drop=True).iterrows():
        if idx > 0 and one_team_per_page:
            story.append(PageBreak())
        elif idx > 0:
            story.append(Spacer(1, 5))

        story.append(Paragraph(f"Team: {esc(row['Team'])}", styles["team"]))
        sections = parse_sections_from_text(row.get(text_col, ""), REQUIRED_SECTIONS)
        for heading in REQUIRED_SECTIONS:
            story.append(Paragraph(esc(heading), styles["heading"]))
            bullets = sections.get(heading) or ["No major items identified."]
            for bullet in bullets:
                story.append(Paragraph("• " + esc(bullet), styles["body"]))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Times-Roman", 8)
        canvas.setFillColor(colors.black)
        canvas.drawCentredString(A4[0] / 2, 18, str(doc_obj.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return str(output_pdf)
