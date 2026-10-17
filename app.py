"""VeriCart — AI-assisted e-commerce return verification demo."""
from __future__ import annotations
import os, uuid, cv2
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory
from dialogflow_agent.chatbot import process_message, reset_session, get_session
from utils.order_db import get_order
from utils.risk_scorer import compute_risk_score
from utils.evidence_engine import analyze_evidence
from utils.case_store import create_case, list_cases, update_case, get_case

app = Flask(__name__)
app.secret_key = os.environ.get("VERICART_SECRET", "vericart-development-secret")
BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
ALLOWED_VIDEOS = {"video/mp4", "video/webm", "video/quicktime", "video/x-msvideo", "video/mpeg"}


def _save_upload(file, session_id):
    ext = Path(file.filename or "evidence").suffix.lower() or ".bin"
    safe = f"{session_id}_{uuid.uuid4().hex[:10]}{ext}"
    path = UPLOADS / safe
    file.save(path)
    return path


def _extract_video_frames(path, max_frames=8):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise ValueError("The uploaded video could not be opened.")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    duration = total / fps if fps else 0
    # Sample evenly, avoiding an enormous upload becoming an enormous analysis.
    indices = [int(i * max(total - 1, 0) / max_frames) for i in range(min(max_frames, max(total, 1)))]
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok and frame is not None:
            ok2, encoded = cv2.imencode(".jpg", frame)
            if ok2: frames.append(encoded.tobytes())
    cap.release()
    if not frames: raise ValueError("No readable frames were found in the video.")
    return frames, {"frame_count": total, "fps": round(fps,2), "duration_seconds": round(duration,2)}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/management")
def management():
    return render_template("management.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    if not message: return jsonify({"error":"Empty message"}), 400
    return jsonify(process_message(message, session_id))


@app.route("/api/verify", methods=["POST"])
def verify():
    if "evidence" not in request.files:
        # Backwards-compatible field name.
        if "image" in request.files: file = request.files["image"]
        else: return jsonify({"success":False,"error":"No evidence uploaded."}), 400
    else:
        file = request.files["evidence"]
    session_id = request.form.get("session_id") or str(uuid.uuid4())
    order_id = (request.form.get("order_id") or "").upper()
    s = get_session(session_id)
    order_id = order_id or s.get("order_id")
    grievance = request.form.get("grievance") or s.get("grievance") or "damage"
    order = get_order(order_id)
    if not order:
        return jsonify({"success":False,"error":"A valid Order ID must be verified before uploading evidence."}), 400

    mime = (file.mimetype or "").lower()
    if mime not in ALLOWED_IMAGES | ALLOWED_VIDEOS:
        return jsonify({"success":False,"error":"Please upload JPG, PNG, WEBP, MP4, WEBM, MOV, or AVI evidence."}), 400
    path = _save_upload(file, session_id)
    try:
        if mime in ALLOWED_VIDEOS:
            frames, video_meta = _extract_video_frames(path)
        else:
            frames, video_meta = [path.read_bytes()], None
        analysis = analyze_evidence(frames, order["product"], order["category"], grievance, order_id, video=bool(video_meta), expected_color=order.get("color"), expected_size=order.get("size"), expected_model=order.get("model"))
    except Exception as exc:
        return jsonify({"success":False,"error":str(exc)}), 400

    risk = compute_risk_score(order_id=order_id)
    # Decision is based on evidence first. Customer risk is contextual and never overrides clear evidence.
    decision = analysis["decision"]
    if decision == "verified_damage":
        final = "approved"
        label = "Return Verified — Damage Confirmed"
    elif decision == "verified_wrong_item":
        final = "approved"
        label = "Return Verified — Wrong Item Confirmed"
    elif decision == "not_verified":
        final = "not_verified"
        label = "No Sufficient Issue Identified"
    elif decision == "request_reupload":
        final = "reupload_required"
        label = "Clearer Evidence Required"
    else:
        final = "human_review"
        label = "Human Verification Required"

    case = None
    if final == "human_review":
        case = create_case({
            "order_id": order_id, "customer_id": order.get("customer_id"),
            "grievance": grievance, "order": order, "risk": risk,
            "analysis": analysis, "evidence_file": path.name,
        })
    s["state"] = "completed"
    result = {
        "success": True, "final_decision": final, "decision_label": label,
        "order": order, "risk": risk, "grievance": grievance,
        "analysis": analysis, "case": case,
        # Compatibility fields for the existing score cards.
        "cnn": {"category": order["category"], "confidence": analysis["product_confidence"], "defect_detected": analysis["damage_detected"]},
        "autoencoder": {"anomaly_score": analysis["anomaly_score"], "is_anomalous": analysis["anomaly_score"] >= 5, "reconstruction_loss": round(analysis["anomaly_score"]/10, 4)},
        "fuzzy": {"decision_score": 2 if final == "approved" else 5 if final == "human_review" else 8},
        "media_type": analysis["media_type"], "evidence_file": path.name,
    }
    return jsonify(result)


@app.route("/api/order/<order_id>")
def order_lookup(order_id):
    order = get_order(order_id)
    if not order: return jsonify({"found":False,"order":None}), 404
    return jsonify({"found":True,"order":order,"risk":compute_risk_score(order_id=order_id)})


@app.route("/api/cases")
def cases():
    return jsonify({"cases":list_cases()})


@app.route("/api/cases/<case_id>", methods=["GET", "PATCH"])
def case_detail(case_id):
    if request.method == "GET":
        item = get_case(case_id)
        return (jsonify(item), 200) if item else (jsonify({"error":"Case not found"}),404)
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in {"APPROVED", "REJECTED", "PENDING"}:
        return jsonify({"error":"status must be APPROVED, REJECTED or PENDING"}),400
    item = update_case(case_id, status, data.get("note", ""))
    return (jsonify(item),200) if item else (jsonify({"error":"Case not found"}),404)


@app.route("/api/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    sid = data.get("session_id")
    if sid: reset_session(sid)
    return jsonify({"status":"reset"})


@app.route("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(UPLOADS, name)


if __name__ == "__main__":
    print("="*60)
    print("VeriCart — AI Return Verification System")
    print("Open http://localhost:5000")
    print("Management queue: http://localhost:5000/management")
    print("="*60)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=True)
