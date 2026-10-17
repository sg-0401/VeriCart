"""Conversation state machine for the VeriCart return assistant."""
from __future__ import annotations
import re
from utils.order_db import get_order
from utils.risk_scorer import compute_risk_score

_sessions = {}

GRIEVANCE_ALIASES = {
    "damage": ["damaged", "damage", "broken", "cracked", "dent", "scratch", "physical damage"],
    "defect": ["defective", "defect", "not working", "malfunction", "faulty", "doesn't work"],
    "wrong_product": ["wrong product", "wrong item", "different product", "different item", "jeans instead", "headphones instead"],
    "wrong_color": ["wrong color", "wrong colour", "different color", "different colour"],
    "wrong_model": ["wrong model", "different model", "model is wrong"],
    "wrong_size": ["wrong size", "different size", "size is wrong", "wrong fit"],
    "other": ["other", "issue", "problem", "grievance", "return"],
}


def get_session(session_id):
    if session_id not in _sessions:
        _sessions[session_id] = {
            "state": "awaiting_grievance", "grievance": None, "order_id": None,
            "order_data": None, "risk_data": None,
        }
    return _sessions[session_id]


def reset_session(session_id):
    _sessions.pop(session_id, None)


def detect_grievance(message):
    m = message.lower()
    for key, words in GRIEVANCE_ALIASES.items():
        if any(w in m for w in words): return key
    return None


def extract_order_id(message):
    m = re.search(r"\b(ORD\s*[-:]?\s*\d{3,6})\b", message.upper())
    return re.sub(r"[^A-Z0-9]", "", m.group(1)) if m else None


def _grievance_label(g):
    return {
        "damage": "Physical Damage", "defect": "Product Defect / Not Working",
        "wrong_product": "Wrong Product", "wrong_color": "Wrong Color",
        "wrong_model": "Wrong Model", "wrong_size": "Wrong Size", "other": "Other Return Issue",
    }.get(g, "Return Issue")


def process_message(message, session_id):
    s = get_session(session_id)
    msg = message.strip()
    intent = detect_grievance(msg)
    reply = ""
    action = "continue"
    show_upload = False
    order_data = None

    if s["state"] == "awaiting_grievance":
        if intent:
            s["grievance"] = intent
            s["state"] = "awaiting_order_id"
            reply = (f"Got it — I've recorded this as **{_grievance_label(intent)}**.\n\n"
                     "Now please enter your **Order ID** so I can identify the exact product you ordered. "
                     "For example: `ORD001`. ")
        else:
            reply = ("I can help verify your return. First, please tell me what went wrong — for example:\n"
                     "• The product is damaged/broken\n• The wrong product was delivered\n"
                     "• Wrong colour, model, or size\n• The product is defective/not working")

    elif s["state"] == "awaiting_order_id":
        oid = extract_order_id(msg)
        if not oid:
            reply = "Please provide the **Order ID** (for example, `ORD001`). I need it before I can verify your evidence."
        else:
            order = get_order(oid)
            if not order:
                reply = f"I couldn't find **{oid}**. Please check the Order ID and try again."
            else:
                risk = compute_risk_score(order_id=oid)
                s.update({"order_id": oid, "order_data": order, "risk_data": risk, "state": "awaiting_evidence"})
                order_data = {**order, "risk": risk}
                action = "order_found"
                show_upload = True
                if s["grievance"] == "wrong_product":
                    evidence_note = "For a wrong-product claim, please include the package/order label in the photo or unboxing video if possible."
                else:
                    evidence_note = "Please upload a clear photo or unboxing video showing the delivered product and the claimed issue."
                reply = (f"✅ Order **{oid}** found.\n\n**Expected product:** {order['product']}\n"
                         f"**Model:** {order.get('model') or 'N/A'} | **Colour:** {order.get('color') or 'N/A'} | **Size:** {order.get('size') or 'N/A'}\n\n"
                         f"{evidence_note}\n\n"
                         "I will first check whether the evidence is clear and whether it actually matches this order before making a decision.")

    elif s["state"] == "awaiting_evidence":
        show_upload = True
        reply = "📸 Please upload the product photo or unboxing video using the evidence uploader below."
        action = "request_evidence"

    else:
        if intent:
            s.update({"state":"awaiting_order_id", "grievance":intent, "order_id":None, "order_data":None})
            reply = f"Sure. I've started a new **{_grievance_label(intent)}** claim. Please provide the Order ID."
        else:
            reply = "Your current case has been analyzed. You can start another return request by describing the new grievance."

    return {"reply": reply, "action": action, "order_data": order_data, "show_upload": show_upload,
            "session_id": session_id, "state": s["state"], "grievance": s.get("grievance"), "order_id": s.get("order_id")}
