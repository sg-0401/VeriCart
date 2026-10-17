# VeriCart — AI E-Commerce Return & Grievance Verification

VeriCart is a Flask prototype for an e-commerce return assistant. It combines a conversational state machine, order lookup, OpenCV-based evidence analysis, optional OCR, video-frame sampling, and a human-review queue.

## Required workflow

**Grievance → Order ID → exact expected product → photo/video evidence → validation → decision**

The system treats these as separate grievances:

- Physical damage / broken product
- Wrong product
- Wrong model
- Wrong colour
- Wrong size
- Product defect / not working

### Evidence rules

1. The Order ID is used to retrieve the exact product, model, colour and size from the order catalogue.
2. Evidence can be a product photo or unboxing video.
3. Blurry/too-small evidence is rejected as **insufficient evidence**, and the user is asked to re-upload instead of being accused of a false claim.
4. The evidence is compared with the expected product using visual feature matching and perceptual similarity.
5. Strong physical-damage evidence can verify a damage claim.
6. A different product is treated as a wrong-product grievance, not as damage.
7. For wrong-product claims, OCR attempts to read the Order ID from the package/evidence. If it cannot be verified, the case is escalated to human management rather than automatically rejected.
8. Wrong colour/model/size are separate grievance paths.
9. Clear evidence can be verified automatically; ambiguous evidence is escalated to `/management`; evidence that clearly does not support a damage claim is reported as **No Sufficient Issue Identified**.

## Run

```powershell
cd Vericart
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**.

Human-review dashboard: **http://localhost:5000/management**.

## Demo orders

- `ORD001` — Sony WH-1000XM5 Headphones — Black
- `ORD003` — Levi's 511 Slim Fit Jeans — Blue — size 32
- `ORD004` — Apple Watch Series 9 — Midnight — 45mm

The bundled clean/damaged/wrong-product images are useful for demonstrating the workflow. The evidence engine recognizes bundled samples by visual signature, not by the filename supplied during upload, so renaming a test image does not bypass the workflow.

## OCR

`pytesseract` is included. For package-label OCR, install the Tesseract OCR application and make sure its executable is available on PATH. If Tesseract is unavailable, the rest of the system still works; package-ID verification will simply remain unavailable and the relevant wrong-product case will be escalated.

## Architecture

```text
Browser
  ↓
Flask API
  ├── Conversation state machine
  ├── Order catalogue
  ├── Evidence upload
  ├── Image quality checks
  ├── Product visual matching
  ├── Damage/anomaly evidence
  ├── OCR / package ID
  └── Human-review case store
       ↓
 APPROVED / RE-UPLOAD / NOT VERIFIED / HUMAN REVIEW
```

## Important limitation

This is a college-project prototype, not a production returns/fraud system. A production deployment should use a properly trained product/variant classifier, a dedicated damage detection/segmentation model, authenticated users, a real order database, secure object storage, audit logs, privacy controls, and thresholds calibrated on representative real-world evidence. The prototype intentionally escalates uncertain cases rather than pretending heuristic computer vision is certain.
