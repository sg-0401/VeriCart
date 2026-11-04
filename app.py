
"""VeriCart — AI-assisted e-commerce return verification demo."""

from __future__ import annotations

import os
import re
import uuid
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import cv2

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
    redirect,
    url_for,
    session,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
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
    "temporary-vericart-development-secret-change-later"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.environ.get("VERICART_HTTPS", "false").lower()
        == "true"
    ),
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24,
)

BASE = Path(__file__).resolve().parent

DATA_DIR = BASE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

DATABASE = DATA_DIR / "users.db"

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
# TEMPORARY SQLITE USER DATABASE
# ============================================================

def get_db():
    """Create a SQLite database connection."""

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    """Create the users table if it does not exist."""

    with get_db() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()


initialize_database()


# ============================================================
# AUTHENTICATION PROTECTION
# ============================================================

@app.before_request
def require_login():
    """
    Protect the dashboard and existing application APIs.

    Login, signup and static files remain publicly accessible.
    """

    public_endpoints = {
        "login",
        "signup",
        "static",
    }

    if request.endpoint in public_endpoints:
        return None

    if session.get("user_id"):
        return None

    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "error": "Please log in to continue.",
            "login_required": True,
        }), 401

    return redirect(
        url_for(
            "login",
            next=request.path
        )
    )


def safe_redirect_target(target):
    """Prevent external redirects after login/signup."""

    if not target:
        return None

    parsed = urlparse(target)

    if parsed.scheme or parsed.netloc:
        return None

    if not target.startswith("/"):
        return None

    if target.startswith("//"):
        return None

    return target


# ============================================================
# SIGNUP
# ============================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":

        name = (request.form.get("name") or "").strip()

        email = (
            request.form.get("email") or ""
        ).strip().lower()

        password = request.form.get("password") or ""

        confirm_password = (
            request.form.get("confirm_password") or ""
        )

        if not name or not email or not password:

            return render_template(
                "signup.html",
                error="Please fill in all the fields."
            )

        if len(name) > 100:

            return render_template(
                "signup.html",
                error="Name must be under 100 characters."
            )

        if not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email
        ):

            return render_template(
                "signup.html",
                error="Please enter a valid email address."
            )

        if len(password) < 8:

            return render_template(
                "signup.html",
                error="Password must contain at least 8 characters."
            )

        if password != confirm_password:

            return render_template(
                "signup.html",
                error="Passwords do not match."
            )

        password_hash = generate_password_hash(password)

        try:

            with get_db() as connection:

                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        name,
                        email,
                        password_hash,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        password_hash,
                        datetime.now().isoformat(timespec="seconds"),
                    )
                )

                user_id = cursor.lastrowid

                connection.commit()

            session.clear()

            session["user_id"] = user_id
            session["user_name"] = name
            session["user_email"] = email
            session.permanent = True

            next_page = safe_redirect_target(
                request.form.get("next")
            )

            return redirect(
                next_page or url_for("index")
            )

        except sqlite3.IntegrityError:

            return render_template(
                "signup.html",
                error="An account with this email already exists."
            )

    return render_template(
        "signup.html",
        next=request.args.get("next", "")
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":

        email = (
            request.form.get("email") or ""
        ).strip().lower()

        password = request.form.get("password") or ""

        with get_db() as connection:

            user = connection.execute(
                """
                SELECT *
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

        if not user or not check_password_hash(
            user["password_hash"],
            password
        ):

            return render_template(
                "login.html",
                error="Incorrect email or password.",
                next=request.form.get("next", "")
            )

        session.clear()

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session.permanent = True

        next_page = safe_redirect_target(
            request.form.get("next")
        )

        return redirect(
            next_page or url_for("index")
        )

    return render_template(
        "login.html",
        next=request.args.get("next", "")
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


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

    return render_template(
        "index.html",
        user_name=session.get("user_name"),
        user_email=session.get("user_email"),
    )


@app.route("/management")
def management():

    return render_template(
        "management.html",
        user_name=session.get("user_name"),
    )


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
        "Signup: http://localhost:5000/signup"
    )

    print(
        "Login: http://localhost:5000/login"
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
