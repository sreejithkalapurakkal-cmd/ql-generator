"""Signal and Brief export service.

Generates:
- Signal report as XLSX (signal timeline + evidence + correlations)
- Brief as PDF-ready HTML (styled for print / wkhtmltopdf)
"""
import logging
from io import BytesIO
from uuid import UUID

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal_event import SignalEvent
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.brief_revision import BriefRevision
from app.models.activity_event import ActivityEvent

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="5C2D8F", end_color="5C2D8F", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
PRIORITY_FILLS = {
    "critical": PatternFill(start_color="FDE8E8", end_color="FDE8E8", fill_type="solid"),
    "high": PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid"),
    "medium": PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid"),
    "low": PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid"),
}
THIN_BORDER = Border(
    left=Side(style="thin", color="E0E0E0"),
    right=Side(style="thin", color="E0E0E0"),
    top=Side(style="thin", color="E0E0E0"),
    bottom=Side(style="thin", color="E0E0E0"),
)


async def generate_signal_report_xlsx(
    db: AsyncSession,
    company_kb_id: UUID,
) -> BytesIO:
    """Generate a styled XLSX signal report for a company."""
    # Fetch company
    kb_result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    company_name = kb.canonical_name if kb else "Unknown"

    # Fetch signals
    result = await db.execute(
        select(SignalEvent)
        .where(SignalEvent.company_kb_id == company_kb_id)
        .order_by(SignalEvent.detected_at.desc())
    )
    signals = list(result.scalars().all())

    # Fetch correlations
    corr_result = await db.execute(
        select(ActivityEvent)
        .where(
            ActivityEvent.company_kb_id == company_kb_id,
            ActivityEvent.event_type == "correlation_found",
        )
        .order_by(ActivityEvent.created_at.desc())
        .limit(20)
    )
    correlations = list(corr_result.scalars().all())

    wb = openpyxl.Workbook()

    # ── Sheet 1: Signal Timeline ──
    ws = wb.active
    ws.title = "Signal Timeline"

    headers = ["Signal Type", "Priority", "Strength", "Title", "Summary",
               "Source", "Source URL", "Evidence Date", "Detected At", "Status"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row_idx, sig in enumerate(signals, 2):
        status = "dismissed" if sig.is_dismissed else "archived" if sig.is_archived else "saved" if sig.is_saved else "active"
        values = [
            sig.signal_type,
            sig.priority,
            sig.strength,
            sig.title,
            (sig.summary or "")[:500],
            sig.source_tool,
            sig.source_url,
            sig.evidence_date.strftime("%Y-%m-%d") if sig.evidence_date else "",
            sig.detected_at.strftime("%Y-%m-%d %H:%M") if sig.detected_at else "",
            status,
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        # Priority row coloring
        fill = PRIORITY_FILLS.get(sig.priority)
        if fill:
            for col in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col).fill = fill

    # Auto-fit columns
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
    ws.column_dimensions["D"].width = 40  # Title
    ws.column_dimensions["E"].width = 50  # Summary

    # ── Sheet 2: Correlations ──
    if correlations:
        ws2 = wb.create_sheet("Correlations")
        corr_headers = ["Correlation", "Narrative", "Confidence", "Date"]
        for col, header in enumerate(corr_headers, 1):
            cell = ws2.cell(row=1, column=col, value=header)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT

        for row_idx, corr in enumerate(correlations, 2):
            detail = corr.technical_detail or {}
            ws2.cell(row=row_idx, column=1, value=detail.get("rule_id", "cluster")).border = THIN_BORDER
            ws2.cell(row=row_idx, column=2, value=corr.narrative).border = THIN_BORDER
            ws2.cell(row=row_idx, column=3, value=corr.confidence).border = THIN_BORDER
            ws2.cell(row=row_idx, column=4, value=corr.created_at.strftime("%Y-%m-%d") if corr.created_at else "").border = THIN_BORDER

        for col in range(1, 5):
            ws2.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 25
        ws2.column_dimensions["B"].width = 60

    # ── Sheet 3: Summary ──
    ws3 = wb.create_sheet("Summary")
    ws3.cell(row=1, column=1, value="Signal Report").font = Font(bold=True, size=14, color="5C2D8F")
    ws3.cell(row=2, column=1, value=f"Company: {company_name}").font = Font(size=12)
    ws3.cell(row=3, column=1, value=f"Total Signals: {len(signals)}")
    ws3.cell(row=4, column=1, value=f"Correlations Found: {len(correlations)}")

    # Priority breakdown
    by_priority = {}
    for s in signals:
        by_priority[s.priority] = by_priority.get(s.priority, 0) + 1
    row = 6
    ws3.cell(row=row, column=1, value="Priority Breakdown").font = Font(bold=True)
    for priority, count in sorted(by_priority.items()):
        row += 1
        ws3.cell(row=row, column=1, value=priority.capitalize())
        ws3.cell(row=row, column=2, value=count)

    # Type breakdown
    by_type = {}
    for s in signals:
        by_type[s.signal_type] = by_type.get(s.signal_type, 0) + 1
    row += 2
    ws3.cell(row=row, column=1, value="Signal Type Breakdown").font = Font(bold=True)
    for sig_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        row += 1
        ws3.cell(row=row, column=1, value=sig_type.replace("_", " ").title())
        ws3.cell(row=row, column=2, value=count)

    # Move Summary to first position
    wb.move_sheet(ws3, offset=-2)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def generate_brief_html(
    db: AsyncSession,
    company_kb_id: UUID,
    version: int | None = None,
) -> str:
    """Generate print-ready HTML for a research brief.

    Returns styled HTML that can be opened in browser and printed to PDF,
    or processed by wkhtmltopdf/weasyprint.
    """
    # Fetch company
    kb_result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    company_name = kb.canonical_name if kb else "Unknown Company"
    domain = kb.normalized_domain if kb else ""

    # Fetch brief
    query = select(BriefRevision).where(BriefRevision.company_kb_id == company_kb_id)
    if version:
        query = query.where(BriefRevision.version == version)
    else:
        query = query.order_by(BriefRevision.version.desc())
    query = query.limit(1)

    result = await db.execute(query)
    brief = result.scalar_one_or_none()

    if not brief:
        return f"<html><body><h1>No brief available for {company_name}</h1></body></html>"

    sections = brief.sections or []

    # Build HTML
    section_html = []
    for section in sections:
        heading = section.get("heading", "")
        body = section.get("body", "")
        bullets = section.get("bullets", [])
        confidence = section.get("confidence", 0)
        insufficient = section.get("insufficient", False)
        sources = section.get("sources", [])

        body_html = f"<p>{_escape(body)}</p>" if body else ""
        if insufficient:
            body_html = '<p class="insufficient">Insufficient data available for this section.</p>'

        bullets_html = ""
        if bullets:
            items = "".join(f"<li>{_escape(b)}</li>" for b in bullets)
            bullets_html = f"<ul>{items}</ul>"

        sources_html = ""
        if sources:
            source_items = []
            for src in sources:
                label = src.get("label", "")
                url = src.get("url", "")
                if url:
                    source_items.append(f'<a href="{_escape(url)}" target="_blank">{_escape(label)}</a>')
                else:
                    source_items.append(_escape(label))
            sources_html = f'<div class="sources">Sources: {" · ".join(source_items)}</div>'

        conf_pct = round(confidence * 100) if confidence else 0
        section_html.append(f"""
        <div class="section">
            <div class="section-header">
                <h2>{_escape(heading)}</h2>
                <span class="confidence">{conf_pct}% confidence</span>
            </div>
            {body_html}
            {bullets_html}
            {sources_html}
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Research Brief — {_escape(company_name)}</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px 20px; color: #333; line-height: 1.6; }}
        .header {{ border-bottom: 3px solid #5C2D8F; padding-bottom: 16px; margin-bottom: 32px; }}
        .header h1 {{ color: #5C2D8F; margin: 0 0 4px; font-size: 24px; }}
        .header .meta {{ color: #888; font-size: 13px; }}
        .section {{ margin-bottom: 28px; page-break-inside: avoid; }}
        .section-header {{ display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #e0e0e0; padding-bottom: 6px; margin-bottom: 12px; }}
        .section h2 {{ color: #333; font-size: 16px; margin: 0; }}
        .confidence {{ color: #888; font-size: 11px; white-space: nowrap; }}
        .section p {{ margin: 0 0 10px; font-size: 14px; }}
        .section ul {{ padding-left: 20px; margin: 0 0 10px; }}
        .section li {{ font-size: 13px; margin-bottom: 4px; }}
        .sources {{ font-size: 11px; color: #999; margin-top: 8px; }}
        .sources a {{ color: #5C2D8F; text-decoration: none; }}
        .insufficient {{ color: #999; font-style: italic; }}
        .footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e0e0e0; font-size: 11px; color: #aaa; }}
        @media print {{ body {{ padding: 20px; }} .section {{ page-break-inside: avoid; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{_escape(company_name)}</h1>
        <div class="meta">
            {_escape(domain)} · Research Brief v{brief.version}
            · {brief.word_count or 0} words · {len(sections)} sections
            · Generated {brief.created_at.strftime('%B %d, %Y') if brief.created_at else 'Unknown date'}
        </div>
    </div>

    {"".join(section_html)}

    <div class="footer">
        Generated by qlGen Research Intelligence · {brief.created_at.strftime('%Y-%m-%d %H:%M UTC') if brief.created_at else ''}
    </div>
</body>
</html>"""

    return html


def _escape(text: str) -> str:
    """Basic HTML escaping."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
