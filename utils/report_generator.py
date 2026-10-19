"""
VeriCart PDF Verification Report Generator.

Converts the technical verification result into a
simple, human-readable return verification report.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)


BASE_DIR = Path(__file__).resolve().parents[1]

REPORT_DIR = BASE_DIR / "data" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe(value, default="Not available"):
    """Return a printable value."""
    if value is None or value == "":
        return default
    return str(value)


def _percentage(value):
    """Convert 0-1 confidence into a percentage."""
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "Not available"


def _decision_text(final_decision):
    """Human-readable explanation of the final decision."""

    mapping = {
        "approved": (
            "The return has been verified successfully. "
            "The available evidence sufficiently supports "
            "the customer's claim."
        ),

        "not_verified": (
            "The uploaded evidence did not provide enough "
            "support for the claimed issue. The expected "
            "product may be present, but the claimed problem "
            "was not sufficiently identified."
        ),

        "reupload_required": (
            "The evidence could not be analysed reliably. "
            "A clearer photograph or video should be uploaded "
            "before making a final return decision."
        ),

        "human_review": (
            "The automated checks produced mixed or uncertain "
            "results. A human specialist should review the "
            "case before the final return decision is made."
        ),
    }

    return mapping.get(
        final_decision,
        "The verification result requires further review."
    )


def _next_action(final_decision):
    """Return the recommended operational next step."""

    mapping = {
        "approved": (
            "Proceed with the return approval process."
        ),

        "not_verified": (
            "The return should not be automatically approved "
            "based on the current evidence. Review the claim "
            "and supporting information if necessary."
        ),

        "reupload_required": (
            "Ask the customer to upload a clearer image or "
            "video showing the complete product and the "
            "claimed issue."
        ),

        "human_review": (
            "Send the case to a verification specialist for "
            "manual review."
        ),
    }

    return mapping.get(
        final_decision,
        "Review the case manually."
    )


def _result_label(final_decision, decision_label):
    """Return a polished report decision heading."""

    if decision_label:
        return decision_label

    mapping = {
        "approved": "RETURN VERIFIED",
        "not_verified": "ISSUE NOT VERIFIED",
        "reupload_required": "CLEARER EVIDENCE REQUIRED",
        "human_review": "HUMAN VERIFICATION REQUIRED",
    }

    return mapping.get(
        final_decision,
        "VERIFICATION RESULT"
    )


def _plain_ai_result(ai_media):
    """
    Convert the AI-media detector output into
    simple language.
    """

    if not ai_media:
        return (
            "AI-generated media analysis was not available."
        )

    status = str(
        ai_media.get("status", "")
    ).lower()

    label = str(
        ai_media.get("label", "")
    ).lower()

    if status == "unavailable":
        return (
            "The AI-generated media check could not be "
            "completed. This did not prevent the other "
            "verification checks from running."
        )

    ai_probability = ai_media.get(
        "ai_probability",
        0
    )

    try:
        probability_text = (
            f"{float(ai_probability) * 100:.1f}%"
        )
    except Exception:
        probability_text = "not available"

    if (
        "ai" in label
        or "generated" in label
    ):
        return (
            f"The media showed characteristics associated "
            f"with AI-generated content. Estimated AI-media "
            f"probability: {probability_text}."
        )

    if (
        "real" in label
        or "authentic" in label
    ):
        return (
            f"The media showed characteristics consistent "
            f"with real photographic/video content. "
            f"Estimated AI-media probability: "
            f"{probability_text}."
        )

    return (
        f"The AI-media detector returned an "
        f"AI-media probability of {probability_text}. "
        f"This result is treated as supporting evidence "
        f"rather than the sole basis for the return decision."
    )


# ============================================================
# MAIN PDF GENERATOR
# ============================================================

def generate_verification_report(
    report_id,
    verification_result,
):
    """
    Generate a PDF verification report.

    Parameters
    ----------
    report_id:
        Unique VeriCart report identifier.

    verification_result:
        The complete JSON result returned by /api/verify.

    Returns
    -------
    Path
        Path to the generated PDF.
    """

    order = (
        verification_result.get("order")
        or {}
    )

    analysis = (
        verification_result.get("analysis")
        or {}
    )

    risk = (
        verification_result.get("risk")
        or {}
    )

    case = (
        verification_result.get("case")
        or {}
    )

    final_decision = (
        verification_result.get(
            "final_decision"
        )
        or analysis.get("decision")
        or "human_review"
    )

    decision_label = (
        verification_result.get(
            "decision_label"
        )
        or ""
    )

    grievance = (
        verification_result.get(
            "grievance"
        )
        or "General return issue"
    )

    now = datetime.now()

    filename = (
        f"VeriCart_Report_"
        f"{report_id}.pdf"
    )

    output_path = REPORT_DIR / filename

    # ========================================================
    # DOCUMENT
    # ========================================================

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="VeriCart Verification Report",
        author="VeriCart",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=27,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
        spaceAfter=8 * mm,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#182230"),
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#30343b"),
        spaceAfter=2.5 * mm,
    )

    small_style = ParagraphStyle(
        "Small",
        parent=body_style,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#666666"),
    )

    decision_style = ParagraphStyle(
        "Decision",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#16202a"),
    )

    # ========================================================
    # STORY
    # ========================================================

    story = []

    # ========================================================
    # HEADER
    # ========================================================

    story.append(
        Paragraph(
            "VERICART",
            title_style
        )
    )

    story.append(
        Paragraph(
            "AI-Assisted Return Verification Report",
            subtitle_style
        )
    )

    # ========================================================
    # REPORT IDENTIFICATION
    # ========================================================

    identification_data = [
        [
            Paragraph("<b>Report ID</b>", body_style),
            Paragraph(
                _safe(report_id),
                body_style
            ),
            Paragraph("<b>Generated</b>", body_style),
            Paragraph(
                now.strftime(
                    "%d %B %Y, %I:%M %p"
                ),
                body_style
            ),
        ],
        [
            Paragraph("<b>Order ID</b>", body_style),
            Paragraph(
                _safe(
                    order.get("order_id")
                    or verification_result.get(
                        "order_id"
                    )
                ),
                body_style
            ),
            Paragraph("<b>Evidence</b>", body_style),
            Paragraph(
                _safe(
                    analysis.get("media_type")
                ).title(),
                body_style
            ),
        ],
    ]

    identification_table = Table(
        identification_data,
        colWidths=[
            27 * mm,
            63 * mm,
            25 * mm,
            57 * mm,
        ],
    )

    identification_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.7,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#E3E7ED"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
        ])
    )

    story.append(
        identification_table
    )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    story.append(
        Paragraph(
            "FINAL VERIFICATION RESULT",
            section_style
        )
    )

    result_text = _result_label(
        final_decision,
        decision_label
    )

    decision_table = Table(
        [
            [
                Paragraph(
                    result_text,
                    decision_style
                )
            ]
        ],
        colWidths=[172 * mm],
    )

    decision_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                colors.HexColor("#EEF4FF"),
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                1,
                colors.HexColor("#B9CBE8"),
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                12,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                12,
            ),
        ])
    )

    story.append(
        decision_table
    )

    story.append(
        Spacer(1, 3 * mm)
    )

    story.append(
        Paragraph(
            _decision_text(
                final_decision
            ),
            body_style
        )
    )

    # ========================================================
    # ORDER DETAILS
    # ========================================================

    story.append(
        Paragraph(
            "1. ORDER & CUSTOMER DETAILS",
            section_style
        )
    )

    customer_name = (
        risk.get("customer_name")
        or order.get("customer_name")
        or order.get("customer")
        or "Not available"
    )

    order_rows = [
        [
            Paragraph("<b>Customer</b>", body_style),
            Paragraph(
                _safe(customer_name),
                body_style
            ),
        ],
        [
            Paragraph("<b>Order ID</b>", body_style),
            Paragraph(
                _safe(
                    order.get("order_id")
                    or verification_result.get(
                        "order_id"
                    )
                ),
                body_style
            ),
        ],
        [
            Paragraph("<b>Product</b>", body_style),
            Paragraph(
                _safe(
                    order.get("product")
                    or analysis.get(
                        "expected_product"
                    )
                ),
                body_style
            ),
        ],
        [
            Paragraph("<b>Category</b>", body_style),
            Paragraph(
                _safe(
                    order.get("category")
                ),
                body_style
            ),
        ],
        [
            Paragraph("<b>Claimed Issue</b>", body_style),
            Paragraph(
                grievance.replace(
                    "_",
                    " "
                ).title(),
                body_style
            ),
        ],
    ]

    order_table = Table(
        order_rows,
        colWidths=[
            42 * mm,
            130 * mm,
        ],
    )

    order_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(order_table)

    # ========================================================
    # WHY THIS RESULT?
    # ========================================================

    story.append(
        Paragraph(
            "2. WHY DID VERICART REACH THIS RESULT?",
            section_style
        )
    )

    reason = (
        analysis.get("reason")
        or "No detailed reason was provided."
    )

    story.append(
        Paragraph(
            reason,
            body_style
        )
    )

    # ========================================================
    # PRODUCT ANALYSIS
    # ========================================================

    story.append(
        Paragraph(
            "3. PRODUCT VERIFICATION",
            section_style
        )
    )

    expected_product = (
        analysis.get(
            "expected_product"
        )
        or order.get("product")
        or "Not available"
    )

    detected_product = (
        analysis.get(
            "detected_product"
        )
        or "Not identified"
    )

    product_confidence = (
        analysis.get(
            "product_confidence"
        )
    )

    product_similarity = (
        analysis.get(
            "expected_product_similarity"
        )
    )

    product_rows = [
        [
            Paragraph(
                "<b>Ordered product</b>",
                body_style
            ),
            Paragraph(
                _safe(expected_product),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Product identified in evidence</b>",
                body_style
            ),
            Paragraph(
                _safe(detected_product),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Product match confidence</b>",
                body_style
            ),
            Paragraph(
                _percentage(product_confidence),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Similarity to ordered product</b>",
                body_style
            ),
            Paragraph(
                _percentage(product_similarity),
                body_style
            ),
        ],
    ]

    product_table = Table(
        product_rows,
        colWidths=[
            65 * mm,
            107 * mm,
        ],
    )

    product_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(product_table)

    # ========================================================
    # DAMAGE ANALYSIS
    # ========================================================

    story.append(
        Paragraph(
            "4. ISSUE / DAMAGE ANALYSIS",
            section_style
        )
    )

    damage_detected = analysis.get(
        "damage_detected",
        False
    )

    damage_confidence = analysis.get(
        "damage_confidence"
    )

    anomaly_score = analysis.get(
        "anomaly_score"
    )

    damage_text = (
        "Visible signs of the claimed physical issue "
        "were identified."
        if damage_detected
        else
        "No sufficient visible evidence of physical "
        "damage was identified."
    )

    damage_rows = [
        [
            Paragraph(
                "<b>Damage detected</b>",
                body_style
            ),
            Paragraph(
                "Yes" if damage_detected else "No",
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Evidence confidence</b>",
                body_style
            ),
            Paragraph(
                _percentage(
                    damage_confidence
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Visual anomaly indicator</b>",
                body_style
            ),
            Paragraph(
                _safe(anomaly_score),
                body_style
            ),
        ],
    ]

    damage_table = Table(
        damage_rows,
        colWidths=[
            65 * mm,
            107 * mm,
        ],
    )

    damage_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(damage_table)

    story.append(
        Spacer(1, 2 * mm)
    )

    story.append(
        Paragraph(
            damage_text,
            body_style
        )
    )

    # ========================================================
    # EVIDENCE QUALITY
    # ========================================================

    story.append(
        Paragraph(
            "5. EVIDENCE QUALITY",
            section_style
        )
    )

    quality = (
        analysis.get("quality")
        or {}
    )

    quality_rows = [
        [
            Paragraph(
                "<b>Evidence type</b>",
                body_style
            ),
            Paragraph(
                _safe(
                    analysis.get(
                        "media_type"
                    )
                ).title(),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Frames analysed</b>",
                body_style
            ),
            Paragraph(
                _safe(
                    analysis.get(
                        "frames_analyzed"
                    ),
                    "1"
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Resolution</b>",
                body_style
            ),
            Paragraph(
                (
                    f"{quality.get('width', 'N/A')} × "
                    f"{quality.get('height', 'N/A')}"
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Sharpness</b>",
                body_style
            ),
            Paragraph(
                _percentage(
                    quality.get(
                        "sharpness_score"
                    )
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Suitable for analysis</b>",
                body_style
            ),
            Paragraph(
                (
                    "Yes"
                    if not quality.get(
                        "is_blurry",
                        False
                    )
                    else
                    "No — evidence may be too blurry"
                ),
                body_style
            ),
        ],
    ]

    quality_table = Table(
        quality_rows,
        colWidths=[
            65 * mm,
            107 * mm,
        ],
    )

    quality_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(
        quality_table
    )

    # ========================================================
    # AI MEDIA
    # ========================================================

    story.append(
        Paragraph(
            "6. AI-GENERATED MEDIA CHECK",
            section_style
        )
    )

    ai_media = analysis.get(
        "ai_media"
    ) or {}

    story.append(
        Paragraph(
            _plain_ai_result(
                ai_media
            ),
            body_style
        )
    )

    # ========================================================
    # OCR / PACKAGE
    # ========================================================

    story.append(
        Paragraph(
            "7. PACKAGE / ORDER INFORMATION",
            section_style
        )
    )

    found_order_ids = (
        analysis.get(
            "order_ids_found"
        )
        or []
    )

    package_match = analysis.get(
        "package_order_match"
    )

    package_text = (
        "An order identifier was successfully "
        "matched to the order."
        if package_match
        else
        "The uploaded evidence did not provide a "
        "confirmed matching order identifier."
    )

    package_rows = [
        [
            Paragraph(
                "<b>Order IDs found in evidence</b>",
                body_style
            ),
            Paragraph(
                ", ".join(found_order_ids)
                if found_order_ids
                else "None detected",
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Order identifier matched</b>",
                body_style
            ),
            Paragraph(
                "Yes" if package_match else "No",
                body_style
            ),
        ],
    ]

    package_table = Table(
        package_rows,
        colWidths=[
            65 * mm,
            107 * mm,
        ],
    )

    package_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(
        package_table
    )

    story.append(
        Spacer(1, 2 * mm)
    )

    story.append(
        Paragraph(
            package_text,
            body_style
        )
    )

    # ========================================================
    # CUSTOMER CONTEXT
    # ========================================================

    story.append(
        Paragraph(
            "8. CUSTOMER CONTEXT",
            section_style
        )
    )

    risk_rows = [
        [
            Paragraph(
                "<b>Risk level</b>",
                body_style
            ),
            Paragraph(
                _safe(
                    risk.get("level")
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Risk score</b>",
                body_style
            ),
            Paragraph(
                _safe(
                    risk.get("score")
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Account age</b>",
                body_style
            ),
            Paragraph(
                (
                    f"{risk.get('account_age_days', 'N/A')} "
                    "days"
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Previous returns</b>",
                body_style
            ),
            Paragraph(
                _safe(
                    risk.get("past_returns")
                ),
                body_style
            ),
        ],
        [
            Paragraph(
                "<b>Fraud flags</b>",
                body_style
            ),
            Paragraph(
                _safe(
                    risk.get("fraud_flags")
                ),
                body_style
            ),
        ],
    ]

    risk_table = Table(
        risk_rows,
        colWidths=[
            65 * mm,
            107 * mm,
        ],
    )

    risk_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D9DEE6"),
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F5F7FA"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(
        risk_table
    )

    story.append(
        Spacer(1, 2 * mm)
    )

    story.append(
        Paragraph(
            "<b>Important:</b> Customer risk is supporting "
            "context only. It should not override clear "
            "evidence about the product or claimed issue.",
            small_style
        )
    )

    # ========================================================
    # CASE INFORMATION
    # ========================================================

    if case:

        story.append(
            Paragraph(
                "9. CASE INFORMATION",
                section_style
            )
        )

        case_rows = [
            [
                Paragraph(
                    "<b>Case ID</b>",
                    body_style
                ),
                Paragraph(
                    _safe(
                        case.get("case_id")
                        or case.get("id")
                    ),
                    body_style
                ),
            ],
            [
                Paragraph(
                    "<b>Case status</b>",
                    body_style
                ),
                Paragraph(
                    _safe(
                        case.get("status")
                    ),
                    body_style
                ),
            ],
        ]

        case_table = Table(
            case_rows,
            colWidths=[
                65 * mm,
                107 * mm,
            ],
        )

        case_table.setStyle(
            TableStyle([
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D9DEE6"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F5F7FA"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ])
        )

        story.append(
            case_table
        )

    # ========================================================
    # NEXT ACTION
    # ========================================================

    story.append(
        Paragraph(
            "10. RECOMMENDED NEXT ACTION",
            section_style
        )
    )

    next_action_table = Table(
        [
            [
                Paragraph(
                    _next_action(
                        final_decision
                    ),
                    body_style
                )
            ]
        ],
        colWidths=[172 * mm],
    )

    next_action_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                colors.HexColor("#F1F8F4"),
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.8,
                colors.HexColor("#B7D8C2"),
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                9,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                9,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                9,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                9,
            ),
        ])
    )

    story.append(
        next_action_table
    )

    # ========================================================
    # TECHNICAL NOTE
    # ========================================================

    story.append(
        Spacer(1, 7 * mm)
    )

    story.append(
        Paragraph(
            "About this report",
            section_style
        )
    )

    story.append(
        Paragraph(
            "VeriCart uses multiple automated checks to "
            "support return verification. These include "
            "image quality assessment, product similarity, "
            "visual evidence analysis, text extraction, "
            "variant checks and AI-generated media analysis. "
            "Automated results are decision-support signals "
            "and may require human review when the evidence "
            "is unclear.",
            small_style
        )
    )

    # ========================================================
    # FOOTER
    # ========================================================

    def add_page_number(canvas, doc):
        canvas.saveState()

        canvas.setFont(
            "Helvetica",
            7.5
        )

        canvas.setFillColor(
            colors.HexColor("#777777")
        )

        canvas.drawCentredString(
            A4[0] / 2,
            8 * mm,
            (
                f"VeriCart • Report {report_id} • "
                f"Page {doc.page}"
            )
        )

        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    return output_path