from io import BytesIO
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def report_filename(summary: dict) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", summary["target_name"].lower()).strip("-")
    return f"lalganjeats-{name}-{summary['period']}-report.pdf"


def render_report_pdf(summary: dict) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"LalganjEats report - {summary['target_name']}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#B91C1C"),
        fontSize=22,
        leading=26,
    )
    story = [
        Paragraph("LalganjEats Partner Report", title_style),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>Partner:</b> {summary['target_name']}", styles["BodyText"]),
        Paragraph(f"<b>Period:</b> {summary['period_label']}", styles["BodyText"]),
        Paragraph(
            f"<b>From:</b> {summary['period_start'].strftime('%d %b %Y, %I:%M %p')} "
            f"&nbsp;&nbsp; <b>To:</b> {summary['period_end'].strftime('%d %b %Y, %I:%M %p')}",
            styles["BodyText"],
        ),
        Paragraph(
            f"<b>Generated:</b> {summary['generated_at'].strftime('%d %b %Y, %I:%M %p')} UTC",
            styles["BodyText"],
        ),
        Spacer(1, 7 * mm),
    ]
    rows = [
        ["Summary", "Value"],
        ["Total orders", str(summary["order_count"])],
        ["Delivered orders", str(summary["delivered_orders"])],
        ["Cancelled orders", str(summary["cancelled_orders"])],
        ["Gross order value", f"INR {summary['gross_order_value']:,.2f}"],
        ["Discounts", f"INR {summary['discounts']:,.2f}"],
        ["Delivery fees", f"INR {summary['delivery_fees']:,.2f}"],
        ["Platform charges", f"INR {summary['platform_charges']:,.2f}"],
        ["Partner gross earnings", f"INR {summary['gross_earnings']:,.2f}"],
        ["Platform fees", f"INR {summary['platform_fees']:,.2f}"],
        ["Settled amount", f"INR {summary['settled_amount']:,.2f}"],
        ["Unsettled amount", f"INR {summary['unsettled_amount']:,.2f}"],
        ["Settled orders", str(summary["settled_orders"])],
        ["Unsettled orders", str(summary["unsettled_orders"])],
    ]
    table = Table(rows, colWidths=[105 * mm, 55 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 8 * mm),
            Paragraph(
                "This report contains aggregate operational and settlement totals only. "
                "It does not contain customer details or individual order records.",
                styles["Italic"],
            ),
        ]
    )
    document.build(story)
    return output.getvalue()
