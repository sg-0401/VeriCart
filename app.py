
"""VeriCart — AI-assisted e-commerce return verification demo."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import cv2

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
)

from dialogflow_agent.chatbot import (
    process_message,
    reset_session,
    get_session,
)

from utils.order_db import get_order
from utils.risk_scorer import compute_risk_score
from utils.evidence_engine import analyze_evidence
from utils.case_store import (
    create_case,
    list_cases,
    update_case,
    get_case,
)
from utils.report_generator import generate_verification_report


app = Flask(__name__)

app.secret_key = os.environ.get(
    "VERICART_SECRET",
    "vericart-development-secret"
)

BASE = Path(__file__).resolve().parent

UPLOADS = BASE / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

AI_MEDIA_THRESHOLD = 0.60

ALLOWED_IMAGES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
}

ALLOWED_VIDEOS = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/mpeg",
}


# ============================================================
# FILE UPLOAD HELPERS
# ============================================================

def _save_upload(file, session_id):
    """Save uploaded evidence using a unique filename."""

    ext = (
        Path(file.filename or "evidence").suffix.lower()
        or ".bin"
    )

    safe = (
        f"{session_id}_"
        f"{uuid.uuid4().hex[:10]}"
        f"{ext}"
    )

    path = UPLOADS / safe

    file.save(path)

    return path


def _extract_video_frames(path, max_frames=8):
    """Extract evenly distributed frames from a video."""

    cap = cv2.VideoCapture(str(path))

    if not cap.isOpened():
        raise ValueError(
            "The uploaded video could not be opened."
        )

    total = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    )

    fps = float(
        cap.get(cv2.CAP_PROP_FPS) or 0
    )

    duration = total / fps if fps else 0

    indices = [
        int(
            i * max(total - 1, 0) / max_frames
        )
        for i in range(
            min(max_frames, max(total, 1))
        )
    ]

    frames = []

    for idx in indices:

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            idx
        )

        ok, frame = cap.read()

        if ok and frame is not None:

            ok2, encoded = cv2.imencode(
                ".jpg",
                frame
            )

            if ok2:
                frames.append(
                    encoded.tobytes()
                )

    cap.release()

    if not frames:
        raise ValueError(
            "No readable frames were found in the video."
        )

    return frames, {
        "frame_count": total,
        "fps": round(fps, 2),
        "duration_seconds": round(duration, 2),
    }


# ============================================================
# DECISION HELPERS
# ============================================================

def _get_ai_probability(analysis):
    """Safely retrieve the AI probability from analysis."""

    ai_media = analysis.get("ai_media") or {}

    try:
        return float(
            ai_media.get("ai_probability", 0)
        )

    except (TypeError, ValueError):
        return 0.0


def _get_normal_decision(analysis):
    """Map existing evidence decisions to final decisions."""

    decision = analysis.get("decision")

    if decision == "verified_damage":

        return (
            "approved",
            "Return Verified — Damage Confirmed"
        )

    if decision == "verified_wrong_item":

        return (
            "approved",
            "Return Verified — Wrong Item Confirmed"
        )

    if decision == "not_verified":

        return (
            "not_verified",
            "No Sufficient Issue Identified"
        )

    if decision == "request_reupload":

        return (
            "reupload_required",
            "Clearer Evidence Required"
        )

    return (
        "human_review",
        "Human Verification Required"
    )


def _create_report_id():
    """Generate a unique verification report ID."""

    return (
        f"VC-{datetime.now().strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:8].upper()}"
    )


def _generate_report(result):
    """Generate a PDF report without breaking verification."""

    try:

        generate_verification_report(
            report_id=result["report_id"],
            verification_result=result,
        )

        result["report_url"] = (
            f"/api/reports/{result['report_id']}/pdf"
        )

    except Exception as exc:

        print(
            "Report generation failed:",
            exc
        )

        result["report_url"] = None


# ============================================================
# RESULT BUILDER
# ============================================================

def _build_result(
    session_id,
    order_id,
    order,
    risk,
    grievance,
    analysis,
    path,
    video_meta,
    final,
    label,
    requires_unboxing_video=False,
    case=None,
):
    """Build a consistent API response for the frontend."""

    report_id = _create_report_id()

    result = {
        "success": True,

        "session_id": session_id,

        "final_decision": final,

        "decision_label": label,

        "requires_unboxing_video":
            requires_unboxing_video,

        "additional_evidence_required":
            requires_unboxing_video,

        "ai_media":
            analysis.get("ai_media", {}),

        "ai_threshold":
            AI_MEDIA_THRESHOLD,

        "order": order,

        "risk": risk,

        "grievance": grievance,

        "analysis": analysis,

        "case": case,

        # Compatibility fields for existing score cards.
        "cnn": {
            "category": order["category"],
            "confidence": analysis["product_confidence"],
            "defect_detected": analysis["damage_detected"],
        },

        "autoencoder": {
            "anomaly_score": analysis["anomaly_score"],
            "is_anomalous": (
                analysis["anomaly_score"] >= 5
            ),
            "reconstruction_loss": round(
                analysis["anomaly_score"] / 10,
                4
            ),
        },

        "fuzzy": {
            "decision_score": (
                2 if final == "approved"
                else 5 if final == "human_review"
                else 8
            ),
        },

        "media_type": analysis["media_type"],

        "video_metadata": video_meta,

        "evidence_file": path.name,

        "report_id": report_id,
    }

    _generate_report(result)

    return result


# ============================================================
# FRONTEND ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/management")
def management():
    return render_template("management.html")


# ============================================================
# CHAT API
# ============================================================

@app.route("/api/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    message = (
        data.get("message") or ""
    ).strip()

    session_id = (
        data.get("session_id")
        or str(uuid.uuid4())
    )

    if not message:
        return jsonify({
            "error": "Empty message"
        }), 400

    return jsonify(
        process_message(
            message,
            session_id
        )
    )


# ============================================================
# EVIDENCE VERIFICATION API
# ============================================================

@app.route("/api/verify", methods=["POST"])
def verify():

    # --------------------------------------------------------
    # 1. RECEIVE UPLOAD
    # --------------------------------------------------------

    if "evidence" not in request.files:

        if "image" in request.files:
            file = request.files["image"]

        else:
            return jsonify({
                "success": False,
                "error": "No evidence uploaded."
            }), 400

    else:

        file = request.files["evidence"]

    session_id = (
        request.form.get("session_id")
        or str(uuid.uuid4())
    )

    order_id = (
        request.form.get("order_id") or ""
    ).upper()

    s = get_session(session_id)

    order_id = order_id or s.get("order_id")

    grievance = (
        request.form.get("grievance")
        or s.get("grievance")
        or "damage"
    )

    order = get_order(order_id)

    if not order:

        return jsonify({
            "success": False,
            "error": (
                "A valid Order ID must be verified "
                "before uploading evidence."
            )
        }), 400

    # --------------------------------------------------------
    # 2. VALIDATE FILE TYPE
    # --------------------------------------------------------

    mime = (
        file.mimetype or ""
    ).lower()

    if mime not in ALLOWED_IMAGES | ALLOWED_VIDEOS:

        return jsonify({
            "success": False,
            "error": (
                "Please upload JPG, PNG, WEBP, "
                "MP4, WEBM, MOV, or AVI evidence."
            )
        }), 400

    is_video = mime in ALLOWED_VIDEOS

    awaiting_video = bool(
        s.get("awaiting_unboxing_video")
    )

    # --------------------------------------------------------
    # 3. REQUIRE VIDEO AFTER A SUSPICIOUS IMAGE
    # --------------------------------------------------------

    if awaiting_video and not is_video:

        return jsonify({
            "success": True,

            "final_decision":
                "additional_evidence_required",

            "decision_label":
                "Unboxing Video Required",

            "requires_unboxing_video": True,

            "additional_evidence_required": True,

            "message": (
                "The previously submitted image crossed "
                "the 60% AI-media threshold. Please upload "
                "an unboxing video so the return can be "
                "verified further. The return has not "
                "been rejected."
            ),

            "ai_media":
                s.get("pending_ai_media", {}),

            "ai_threshold":
                AI_MEDIA_THRESHOLD,

            "session_id":
                session_id,
        })

    # --------------------------------------------------------
    # 4. SAVE UPLOAD
    # --------------------------------------------------------

    path = _save_upload(
        file,
        session_id
    )

    try:

        if is_video:

            frames, video_meta = (
                _extract_video_frames(path)
            )

        else:

            frames = [
                path.read_bytes()
            ]

            video_meta = None

        # ----------------------------------------------------
        # 5. RUN EXISTING EVIDENCE ANALYSIS
        # ----------------------------------------------------

        analysis = analyze_evidence(
            frames,
            order["product"],
            order["category"],
            grievance,
            order_id,
            video=is_video,
            expected_color=order.get("color"),
            expected_size=order.get("size"),
            expected_model=order.get("model"),
        )

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    # --------------------------------------------------------
    # 6. AI MEDIA THRESHOLD
    # --------------------------------------------------------

    ai_media = analysis.get(
        "ai_media",
        {}
    )

    ai_probability = _get_ai_probability(
        analysis
    )

    ai_detection_available = (
        ai_media.get("status") != "unavailable"
        and "error" not in ai_media
    )

    suspicious_media = (
        ai_detection_available
        and ai_probability >= AI_MEDIA_THRESHOLD
    )

    risk = compute_risk_score(
        order_id=order_id
    )

    # --------------------------------------------------------
    # 7. IMAGE CROSSED 60%: REQUEST UNBOXING VIDEO
    # --------------------------------------------------------

    if suspicious_media and not is_video:

        s["state"] = "awaiting_unboxing_video"

        s["awaiting_unboxing_video"] = True

        s["pending_ai_media"] = ai_media

        s["pending_order_id"] = order_id

        s["pending_grievance"] = grievance

        result = _build_result(
            session_id=session_id,
            order_id=order_id,
            order=order,
            risk=risk,
            grievance=grievance,
            analysis=analysis,
            path=path,
            video_meta=video_meta,
            final="additional_evidence_required",
            label="Unboxing Video Required",
            requires_unboxing_video=True,
        )

        result["message"] = (
            "The uploaded image has an AI-generated "
            "media probability of "
            f"{ai_probability * 100:.1f}%, which meets "
            "or exceeds the 60% threshold. Please upload "
            "an unboxing video for further verification. "
            "This is an additional evidence request, "
            "not a rejection."
        )

        return jsonify(result)

    # --------------------------------------------------------
    # 8. VIDEO CROSSED 60%: HUMAN REVIEW
    # --------------------------------------------------------

    if suspicious_media and is_video:

        final = "human_review"

        label = (
            "Human Verification Required — "
            "Media Needs Further Review"
        )

        case = create_case({
            "order_id": order_id,
            "customer_id": order.get("customer_id"),
            "grievance": grievance,
            "order": order,
            "risk": risk,
            "analysis": analysis,
            "evidence_file": path.name,
        })

        s["state"] = "completed"

        s["awaiting_unboxing_video"] = False

        s.pop(
            "pending_ai_media",
            None
        )

        result = _build_result(
            session_id=session_id,
            order_id=order_id,
            order=order,
            risk=risk,
            grievance=grievance,
            analysis=analysis,
            path=path,
            video_meta=video_meta,
            final=final,
            label=label,
            case=case,
        )

        result["message"] = (
            "The unboxing video also crossed the "
            "60% AI-media threshold. The return has "
            "been sent for human verification. "
            "It has not been automatically rejected."
        )

        return jsonify(result)

    # --------------------------------------------------------
    # 9. NORMAL VERIFICATION
    # --------------------------------------------------------

    final, label = _get_normal_decision(
        analysis
    )

    case = None

    if final == "human_review":

        case = create_case({
            "order_id": order_id,
            "customer_id": order.get("customer_id"),
            "grievance": grievance,
            "order": order,
            "risk": risk,
            "analysis": analysis,
            "evidence_file": path.name,
        })

    s["state"] = "completed"

    s["awaiting_unboxing_video"] = False

    s.pop(
        "pending_ai_media",
        None
    )

    # --------------------------------------------------------
    # 10. BUILD FINAL RESULT AND PDF
    # --------------------------------------------------------

    result = _build_result(
        session_id=session_id,
        order_id=order_id,
        order=order,
        risk=risk,
        grievance=grievance,
        analysis=analysis,
        path=path,
        video_meta=video_meta,
        final=final,
        label=label,
        case=case,
    )

    result["message"] = (
        "Normal evidence verification completed."
        if ai_detection_available
        else
        "AI-media detection was unavailable. "
        "Normal evidence verification was continued."
    )

    return jsonify(result)


# ============================================================
# ORDER LOOKUP
# ============================================================

@app.route("/api/order/<order_id>")
def order_lookup(order_id):

    order = get_order(order_id)

    if not order:

        return jsonify({
            "found": False,
            "order": None
        }), 404

    return jsonify({
        "found": True,
        "order": order,
        "risk": compute_risk_score(
            order_id=order_id
        )
    })


# ============================================================
# CASE MANAGEMENT
# ============================================================

@app.route("/api/cases")
def cases():

    return jsonify({
        "cases": list_cases()
    })


@app.route(
    "/api/cases/<case_id>",
    methods=["GET", "PATCH"]
)
def case_detail(case_id):

    if request.method == "GET":

        item = get_case(case_id)

        return (
            jsonify(item), 200
        ) if item else (
            jsonify({
                "error": "Case not found"
            }), 404
        )

    data = request.get_json(
        silent=True
    ) or {}

    status = data.get("status")

    if status not in {
        "APPROVED",
        "REJECTED",
        "PENDING",
    }:

        return jsonify({
            "error": (
                "status must be APPROVED, "
                "REJECTED or PENDING"
            )
        }), 400

    item = update_case(
        case_id,
        status,
        data.get("note", "")
    )

    return (
        jsonify(item), 200
    ) if item else (
        jsonify({
            "error": "Case not found"
        }), 404
    )


# ============================================================
# SESSION RESET
# ============================================================

@app.route("/api/reset", methods=["POST"])
def reset():

    data = request.get_json(
        silent=True
    ) or {}

    sid = data.get("session_id")

    if sid:

        reset_session(sid)

        # Clear the additional evidence state too.
        s = get_session(sid)

        s.pop(
            "awaiting_unboxing_video",
            None
        )

        s.pop(
            "pending_ai_media",
            None
        )

        s["state"] = "reset"

    return jsonify({
        "status": "reset"
    })


# ============================================================
# PDF REPORT DOWNLOAD
# ============================================================

@app.route("/api/reports/<report_id>/pdf")
def download_report(report_id):

    filename = (
        f"VeriCart_Report_{report_id}.pdf"
    )

    report_path = (
        BASE
        / "data"
        / "reports"
        / filename
    )

    if not report_path.exists():

        return jsonify({
            "success": False,
            "error": "Verification report not found."
        }), 404

    return send_from_directory(
        report_path.parent,
        report_path.name,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ============================================================
# UPLOADED EVIDENCE
# ============================================================

@app.route("/uploads/<path:name>")
def uploaded(name):

    return send_from_directory(
        UPLOADS,
        name
    )


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    print("=" * 60)

    print(
        "VeriCart — AI Return Verification System"
    )

    print(
        "Open http://localhost:5000"
    )

    print(
        "Management queue: http://localhost:5000/management"
    )

    print(
        "AI-media threshold: 60%"
    )

    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True,
    )
