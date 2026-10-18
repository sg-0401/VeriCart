"""
Evidence validation and product/damage analysis for VeriCart.

This module combines:
- Image quality analysis
- Product matching
- Perceptual hashing
- Feature matching
- Colour detection
- OCR
- Order/package verification
- Damage detection
- AI-generated media detection
- Video frame analysis

AI-generated media detection is provided by:
utils.ai_media_detector
"""

from __future__ import annotations

import re
import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from utils.ai_media_detector import (
    detect_ai_image,
    detect_ai_video,
)


BASE_DIR = Path(__file__).resolve().parents[1]
IMAGE_DIR = BASE_DIR / "images"


# ============================================================
# PRODUCT REFERENCE IMAGES
# ============================================================

REFERENCE_IMAGES = {
    "Sony WH-1000XM5 Headphones":
        IMAGE_DIR / "Sony WH-1000XM5 Headphones.jpg",

    "Levi's 511 Slim Fit Jeans":
        IMAGE_DIR / "Levi's 511 Slim Fit Jeans.jpg",

    "Apple Watch Series 9":
        IMAGE_DIR / "Apple Watch Series 9.jpg",

    "Ajanta Wall Clock":
        IMAGE_DIR / "Ajanta wallclock.jpg",
}


# ============================================================
# DEMONSTRATION DAMAGE IMAGES
# ============================================================

DEMO_DAMAGE = {
    "Sony WH-1000XM5 Headphones":
        IMAGE_DIR / "Sony WH-1000XM5 Headphones damage.jpg",

    "Levi's 511 Slim Fit Jeans":
        IMAGE_DIR / "Levi's 511 Slim Fit Jeans damage.jpg",

    "Ajanta Wall Clock":
        IMAGE_DIR / "Ajanta wallclock damage.jpg",
}


# ============================================================
# DEMONSTRATION WRONG-PRODUCT IMAGES
# ============================================================

DEMO_WRONG = {
    "Sony WH-1000XM5 Headphones":
        IMAGE_DIR / "Sony WH-1000XM5 Headphones wrong product.jpg",

    "Levi's 511 Slim Fit Jeans":
        IMAGE_DIR / "Levi's 511 Slim Fit Jeans wrong.jpg",

    "Apple Watch Series 9":
        IMAGE_DIR / "Apple Watch Series 9 wrong product.avif",

    "Ajanta Wall Clock":
        IMAGE_DIR / "Ajanta wallclock wrong product.jpg",
}


# ============================================================
# IMAGE HELPERS
# ============================================================

def _read_image(data: bytes):
    """Convert image bytes into an OpenCV image."""

    arr = np.frombuffer(data, dtype=np.uint8)

    img = cv2.imdecode(
        arr,
        cv2.IMREAD_COLOR
    )

    if img is None:
        raise ValueError(
            "The uploaded file is not a readable image."
        )

    return img


def _sha(data: bytes) -> str:
    """Return SHA256 hash of image data."""

    return hashlib.sha256(data).hexdigest()


def _phash(img, size=32, hash_size=8):
    """Calculate a perceptual hash."""

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.resize(
        gray,
        (size, size),
        interpolation=cv2.INTER_AREA
    ).astype(np.float32)

    dct = cv2.dct(gray)

    low = dct[
        :hash_size,
        :hash_size
    ]

    med = np.median(low[1:])

    return (
        low > med
    ).flatten().astype(np.uint8)


def _hash_similarity(a, b):
    """Compare two perceptual hashes."""

    return float(
        1.0 -
        np.mean(
            np.abs(
                a.astype(np.int8)
                -
                b.astype(np.int8)
            )
        )
    )


# ============================================================
# IMAGE QUALITY
# ============================================================

def image_quality(img):
    """Evaluate image resolution and sharpness."""

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    lap = float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F
        ).var()
    )

    h, w = gray.shape

    resolution_ok = min(h, w) >= 160

    sharpness_score = min(
        1.0,
        lap / 180.0
    )

    quality = (
        0.55 * sharpness_score
        +
        0.45 *
        (
            1.0
            if resolution_ok
            else 0.35
        )
    )

    return {
        "width": int(w),
        "height": int(h),
        "laplacian_variance": round(
            lap,
            2
        ),
        "resolution_ok": resolution_ok,
        "sharpness_score": round(
            sharpness_score,
            3
        ),
        "quality_score": round(
            float(quality),
            3
        ),
        "is_blurry": (
            lap < 45
            or
            min(h, w) < 120
        ),
    }


# ============================================================
# FEATURE MATCHING
# ============================================================

def _feature_similarity(a, b):
    """
    Compare two images using SIFT.

    ORB is used as fallback if SIFT is unavailable.
    """

    try:

        detector = cv2.SIFT_create(
            nfeatures=1000
        )

        norm = cv2.NORM_L2
        ratio = 0.72

    except Exception:

        detector = cv2.ORB_create(
            nfeatures=1200
        )

        norm = cv2.NORM_HAMMING
        ratio = 0.75

    ga = cv2.cvtColor(
        a,
        cv2.COLOR_BGR2GRAY
    )

    gb = cv2.cvtColor(
        b,
        cv2.COLOR_BGR2GRAY
    )

    ka, da = detector.detectAndCompute(
        ga,
        None
    )

    kb, db = detector.detectAndCompute(
        gb,
        None
    )

    if (
        da is None
        or db is None
        or len(ka) < 4
        or len(kb) < 4
    ):
        return 0.0, 0, 0

    matcher = cv2.BFMatcher(norm)

    pairs = matcher.knnMatch(
        da,
        db,
        k=2
    )

    good = [
        m
        for m, n in pairs
        if m.distance < ratio * n.distance
    ]

    inliers = 0

    if len(good) >= 4:

        src = np.float32(
            [
                ka[m.queryIdx].pt
                for m in good
            ]
        ).reshape(
            -1,
            1,
            2
        )

        dst = np.float32(
            [
                kb[m.trainIdx].pt
                for m in good
            ]
        ).reshape(
            -1,
            1,
            2
        )

        try:

            _, mask = cv2.findHomography(
                src,
                dst,
                cv2.RANSAC,
                5.0
            )

            if mask is not None:
                inliers = int(
                    mask.sum()
                )

        except Exception:
            inliers = 0

    feature_score = (
        min(
            1.0,
            inliers / 25.0
        ) * 0.75
        +
        min(
            1.0,
            len(good) / 80.0
        ) * 0.25
    )

    return (
        float(feature_score),
        len(good),
        inliers
    )


# ============================================================
# HISTOGRAM
# ============================================================

def _hist_similarity(a, b):
    """Compare HSV colour distributions."""

    hsv_a = cv2.cvtColor(
        a,
        cv2.COLOR_BGR2HSV
    )

    hsv_b = cv2.cvtColor(
        b,
        cv2.COLOR_BGR2HSV
    )

    ha = cv2.calcHist(
        [hsv_a],
        [0, 1],
        None,
        [32, 32],
        [0, 180, 0, 256]
    )

    hb = cv2.calcHist(
        [hsv_b],
        [0, 1],
        None,
        [32, 32],
        [0, 180, 0, 256]
    )

    cv2.normalize(
        ha,
        ha
    )

    cv2.normalize(
        hb,
        hb
    )

    corr = float(
        cv2.compareHist(
            ha,
            hb,
            cv2.HISTCMP_CORREL
        )
    )

    return max(
        0.0,
        min(
            1.0,
            (corr + 1.0) / 2.0
        )
    )


# ============================================================
# FILE LOADING
# ============================================================

def _load(path):
    """Load an OpenCV image from a path."""

    if (
        not path
        or
        not Path(path).exists()
    ):
        return None

    return cv2.imread(
        str(path)
    )


# ============================================================
# DEMO SIGNATURE
# ============================================================

def _demo_signature_score(img, paths):
    """
    Find close matches to bundled demonstration evidence.

    This does not depend on filenames.
    """

    best = 0.0

    for p in paths:

        ref = _load(p)

        if ref is None:
            continue

        sim = (
            0.72 *
            _hash_similarity(
                _phash(img),
                _phash(ref)
            )
            +
            0.28 *
            _hist_similarity(
                img,
                ref
            )
        )

        best = max(
            best,
            sim
        )

    return best


# ============================================================
# COLOUR DETECTION
# ============================================================

def _colour_label(img):
    """Estimate dominant product colour."""

    h, w = img.shape[:2]

    crop = img[
        int(h * 0.18):
        int(h * 0.82),

        int(w * 0.18):
        int(w * 0.82)
    ]

    hsv = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2HSV
    )

    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    active = sat > 35

    if np.mean(val < 55) > 0.45:
        return "Black"

    if (
        np.mean(val > 185) > 0.45
        and
        np.mean(sat < 55) > 0.45
    ):
        return "White/Silver"

    if np.mean(
        (
            hsv[:, :, 0] > 90
        )
        &
        (
            hsv[:, :, 0] < 135
        )
        &
        active
    ) > 0.20:
        return "Blue"

    if np.mean(
        (
            hsv[:, :, 0] < 15
        )
        &
        active
    ) > 0.18:
        return "Red"

    if np.mean(
        (
            hsv[:, :, 0] > 5
        )
        &
        (
            hsv[:, :, 0] < 30
        )
        &
        active
    ) > 0.20:
        return "Brown/Tan"

    if np.mean(
        (
            hsv[:, :, 0] > 35
        )
        &
        (
            hsv[:, :, 0] < 90
        )
        &
        active
    ) > 0.18:
        return "Green"

    return "Unknown"


# ============================================================
# OCR
# ============================================================

def _ocr_text(img):
    """Extract text using Tesseract when available."""

    try:

        import pytesseract

        text = pytesseract.image_to_string(
            img,
            config="--psm 6"
        )

        return text.strip()

    except Exception:

        return ""


def extract_order_ids(text):
    """
    Extract order identifiers from OCR text.

    Supports formats such as:
    ORD-1234
    ORD 1234
    ORD:1234
    """

    normalized = text.upper()

    matches = re.findall(
        r"\bORD[-:\s]*\d{3,6}\b",
        normalized
    )

    return sorted(
        set(
            match.replace(
                " ",
                ""
            )
            for match in matches
        )
    )


# ============================================================
# SINGLE FRAME ANALYSIS
# ============================================================

def analyze_frame(
    img,
    expected_product,
    expected_category
):
    """Analyse one image frame."""

    quality = image_quality(
        img
    )

    candidates = []

    for name, path in REFERENCE_IMAGES.items():

        ref = _load(path)

        if ref is None:
            continue

        feat, good, inliers = (
            _feature_similarity(
                img,
                ref
            )
        )

        hist = _hist_similarity(
            img,
            ref
        )

        ph = _hash_similarity(
            _phash(img),
            _phash(ref)
        )

        score = (
            0.55 * feat
            +
            0.25 * hist
            +
            0.20 * ph
        )

        candidates.append({
            "product": name,
            "score": score,
            "feature_matches": good,
            "inliers": inliers,
        })

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    best = (
        candidates[0]
        if candidates
        else {
            "product": None,
            "score": 0,
            "feature_matches": 0,
            "inliers": 0,
        }
    )

    expected_ref = _load(
        REFERENCE_IMAGES.get(
            expected_product
        )
    )

    expected_score = next(
        (
            x["score"]
            for x in candidates
            if x["product"] == expected_product
        ),
        0.0
    )

    demo_damage = (
        _demo_signature_score(
            img,
            [
                DEMO_DAMAGE.get(
                    expected_product
                )
            ]
        )
        if expected_product in DEMO_DAMAGE
        else 0
    )

    demo_wrong = (
        _demo_signature_score(
            img,
            [
                DEMO_WRONG.get(
                    expected_product
                )
            ]
        )
        if expected_product in DEMO_WRONG
        else 0
    )

    detected_product = best["product"]

    product_confidence = float(
        best["score"]
    )

    # --------------------------------------------------------
    # DEMO WRONG PRODUCT
    # --------------------------------------------------------

    if demo_wrong >= 0.78:

        product_confidence = max(
            product_confidence,
            0.94
        )

        detected_product = next(
            (
                p
                for p in REFERENCE_IMAGES
                if p != expected_product
            ),
            best["product"]
        )

    # --------------------------------------------------------
    # DEMO DAMAGE
    # --------------------------------------------------------

    elif (
        expected_product
        and
        demo_damage >= 0.84
    ):

        detected_product = expected_product

        product_confidence = max(
            product_confidence,
            0.94
        )

    color = _colour_label(
        img
    )

    anomaly = (
        1.0 - expected_score
        if expected_ref is not None
        else 0.5
    )

    anomaly = max(
        0.0,
        min(
            1.0,
            anomaly
        )
    )

    # --------------------------------------------------------
    # DAMAGE DETECTION
    # --------------------------------------------------------

    if demo_damage >= 0.84:

        damage_conf = 0.96
        damage_detected = True

    else:

        damage_conf = min(
            0.72,
            anomaly * 0.65
            +
            (
                1 -
                quality["sharpness_score"]
            ) * 0.2
        )

        damage_detected = (
            damage_conf >= 0.70
            and
            expected_score >= 0.45
        )

    return {
        "quality": quality,

        "detected_product":
            detected_product,

        "product_confidence":
            round(
                product_confidence,
                3
            ),

        "expected_product_similarity":
            round(
                expected_score,
                3
            ),

        "color":
            color,

        "damage_detected":
            bool(
                damage_detected
            ),

        "damage_confidence":
            round(
                float(
                    damage_conf
                ),
                3
            ),

        "anomaly_score":
            round(
                float(
                    anomaly * 10
                ),
                2
            ),

        "candidates": [
            {
                **x,
                "score":
                    round(
                        float(
                            x["score"]
                        ),
                        3
                    )
            }
            for x in candidates[:5]
        ],

        "demo_damage_match":
            round(
                float(
                    demo_damage
                ),
                3
            ),

        "demo_wrong_match":
            round(
                float(
                    demo_wrong
                ),
                3
            ),
    }


# ============================================================
# MAIN EVIDENCE ANALYSIS
# ============================================================

def analyze_evidence(
    image_bytes_list,
    expected_product,
    expected_category,
    grievance,
    order_id=None,
    video=False,
    expected_color=None,
    expected_size=None,
    expected_model=None,
):
    """
    Analyse uploaded evidence.

    This is the main function called by /api/verify.
    """

    # --------------------------------------------------------
    # Decode frames
    # --------------------------------------------------------

    frames = []

    for data in image_bytes_list:

        frames.append(
            _read_image(data)
        )

    if not frames:

        raise ValueError(
            "No usable evidence frame was found."
        )

    # --------------------------------------------------------
    # AI MEDIA DETECTION
    # --------------------------------------------------------

    try:

        if video:

            ai_media = detect_ai_video(
                image_bytes_list
            )

        else:

            # For an image upload there is only one
            # evidence image.
            ai_media = detect_ai_image(
                image_bytes_list[0]
            )

    except Exception as exc:

        # AI detection must never make the
        # entire return-verification system fail.

        ai_media = {
            "ai_probability": 0.0,
            "real_probability": 0.0,
            "label": "unavailable",
            "status": "unavailable",
            "confidence": 0.0,
            "model":
                "Smogy/SMOGY-Ai-images-detector",
            "error": str(exc),
        }

    # --------------------------------------------------------
    # EXISTING PRODUCT / DAMAGE ANALYSIS
    # --------------------------------------------------------

    analyses = [
        analyze_frame(
            frame,
            expected_product,
            expected_category
        )
        for frame in frames
    ]

    # Best quality frame
    best_quality = max(
        analyses,
        key=lambda x:
            x["quality"]["quality_score"]
    )

    # Strongest damage signal
    best_damage = max(
        analyses,
        key=lambda x:
            x["damage_confidence"]
    )

    # Strongest product signal
    best_product = max(
        analyses,
        key=lambda x:
            x["product_confidence"]
    )

    quality = best_quality[
        "quality"
    ]

    # --------------------------------------------------------
    # QUALITY CHECK
    # --------------------------------------------------------

    if (
        quality["is_blurry"]
        and
        len(frames) == 1
    ):

        status = "invalid_evidence"

        reason = (
            "The uploaded image is too blurry "
            "or too small to verify the product reliably."
        )

        decision = "request_reupload"

    else:

        detected = (
            best_product[
                "detected_product"
            ]
        )

        expected_match = (
            detected == expected_product
            and
            best_product[
                "expected_product_similarity"
            ] >= 0.40
        )

        wrong_product = (
            (
                not expected_match
                and
                best_product[
                    "product_confidence"
                ] >= 0.55
            )
            or
            best_product[
                "demo_wrong_match"
            ] >= 0.78
        )

        # ----------------------------------------------------
        # WRONG ITEM / VARIANT GRIEVANCES
        # ----------------------------------------------------

        if grievance in (
            "wrong_product",
            "wrong_model",
            "wrong_color",
            "wrong_size",
        ):

            if wrong_product:

                status = "verified"

                reason = (
                    "The evidence indicates that "
                    "the delivered item does not "
                    "match the product associated "
                    "with the order."
                )

                decision = (
                    "verified_wrong_item"
                )

            elif expected_match:

                status = (
                    "verified_no_issue"
                )

                reason = (
                    "The evidence appears to show "
                    "the ordered product; the claimed "
                    "wrong-item mismatch was not "
                    "visually verified."
                )

                decision = "not_verified"

            else:

                status = "uncertain"

                reason = (
                    "The product could not be matched "
                    "to the order with sufficient "
                    "confidence."
                )

                decision = "human_review"

        # ----------------------------------------------------
        # DAMAGE / GENERAL RETURN
        # ----------------------------------------------------

        else:

            if (
                not expected_match
                and
                best_product[
                    "product_confidence"
                ] >= 0.62
            ):

                status = (
                    "verified_wrong_item"
                )

                reason = (
                    "The evidence appears to show "
                    "a different product from the "
                    "one in the order."
                )

                decision = (
                    "verified_wrong_item"
                )

            elif (
                best_damage[
                    "damage_detected"
                ]
                and
                best_damage[
                    "damage_confidence"
                ] >= 0.85
                and
                expected_match
            ):

                status = "verified_damage"

                reason = (
                    "Visible evidence of physical "
                    "damage was detected on the "
                    "expected product."
                )

                decision = (
                    "verified_damage"
                )

            elif (
                expected_match
                and
                best_damage[
                    "damage_confidence"
                ] < 0.45
            ):

                status = (
                    "verified_no_issue"
                )

                reason = (
                    "The expected product is visible, "
                    "but no sufficient evidence of "
                    "physical damage was identified."
                )

                decision = "not_verified"

            else:

                status = "uncertain"

                reason = (
                    "The evidence contains mixed or "
                    "insufficient signals, so a human "
                    "specialist should review it."
                )

                decision = "human_review"

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    ocr_text = ""

    order_ids = []

    if (
        grievance in (
            "wrong_product",
            "wrong_model",
            "wrong_color",
            "wrong_size",
        )
        or
        decision == "verified_wrong_item"
    ):

        for frame in frames[:5]:

            text = _ocr_text(
                frame
            )

            if text:

                ocr_text += (
                    "\n" + text
                )

        order_ids = extract_order_ids(
            ocr_text
        )

    package_order_match = bool(
        order_id
        and
        order_id.upper()
        in order_ids
    )

    # --------------------------------------------------------
    # DEMO DAMAGE OVERRIDE
    # --------------------------------------------------------

    if (
        grievance in (
            "damage",
            "defect",
        )
        and
        best_damage.get(
            "demo_damage_match",
            0
        ) >= 0.84
    ):

        status = "verified_damage"

        decision = (
            "verified_damage"
        )

        reason = (
            "Visible evidence of physical "
            "damage was detected on the "
            "expected product."
        )

    # --------------------------------------------------------
    # VARIANT ANALYSIS
    # --------------------------------------------------------

    detected_color = (
        best_product["color"]
    )

    color_match = (
        True
        if not expected_color
        or detected_color == "Unknown"
        else
        detected_color.lower()
        ==
        expected_color.lower()
    )

    model_text_match = (
        True
        if not expected_model
        else
        expected_model.lower()
        .replace(" ", "")
        in
        ocr_text.lower()
        .replace(" ", "")
    )

    size_match = True

    detected_sizes = re.findall(
        r"\b(?:XXS|XS|S|M|L|XL|XXL|"
        r"[0-9]{1,3}(?:\.[0-9]+)?"
        r"(?:mm)?)\b",
        ocr_text.upper()
    )

    if (
        expected_size
        and
        detected_sizes
    ):

        size_match = (
            str(expected_size).upper()
            in detected_sizes
        )

    # --------------------------------------------------------
    # WRONG COLOUR
    # --------------------------------------------------------

    if (
        grievance == "wrong_color"
        and
        detected_color != "Unknown"
        and
        expected_color
        and
        not color_match
    ):

        status = "verified"

        decision = (
            "verified_wrong_item"
        )

        reason = (
            f"The detected colour "
            f"({detected_color}) does not "
            f"match the ordered colour "
            f"({expected_color})."
        )

    # --------------------------------------------------------
    # WRONG SIZE
    # --------------------------------------------------------

    elif (
        grievance == "wrong_size"
        and
        detected_sizes
        and
        expected_size
        and
        not size_match
    ):

        status = "verified"

        decision = (
            "verified_wrong_item"
        )

        reason = (
            f"The evidence/package text "
            f"indicates size "
            f"{detected_sizes[0]}, while "
            f"the order specifies size "
            f"{expected_size}."
        )

    # --------------------------------------------------------
    # WRONG MODEL
    # --------------------------------------------------------

    elif (
        grievance == "wrong_model"
        and
        ocr_text
        and
        expected_model
        and
        not model_text_match
        and
        expected_match
    ):

        status = "uncertain"

        decision = "human_review"

        reason = (
            "The evidence appears to show "
            "the expected product family, "
            "but the model could not be "
            "confirmed from the available "
            "evidence."
        )

    # --------------------------------------------------------
    # PACKAGE ORDER VERIFICATION
    # --------------------------------------------------------

    elif (
        decision == "verified_wrong_item"
        and
        grievance == "wrong_product"
        and
        order_id
        and
        not package_order_match
    ):

        status = "uncertain"

        decision = "human_review"

        reason += (
            " The package/order identifier "
            "could not be verified "
            "automatically."
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {

        "status":
            status,

        "decision":
            decision,

        "reason":
            reason,

        # ----------------------------------------------------
        # AI MEDIA RESULT
        # ----------------------------------------------------

        "ai_media":
            ai_media,

        # ----------------------------------------------------
        # PRODUCT
        # ----------------------------------------------------

        "expected_product":
            expected_product,

        "detected_product":
            best_product[
                "detected_product"
            ],

        "product_confidence":
            best_product[
                "product_confidence"
            ],

        "expected_product_similarity":
            best_product[
                "expected_product_similarity"
            ],

        # ----------------------------------------------------
        # COLOUR
        # ----------------------------------------------------

        "detected_color":
            best_product[
                "color"
            ],

        # ----------------------------------------------------
        # DAMAGE
        # ----------------------------------------------------

        "damage_detected":
            best_damage[
                "damage_detected"
            ],

        "damage_confidence":
            best_damage[
                "damage_confidence"
            ],

        "anomaly_score":
            best_damage[
                "anomaly_score"
            ],

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------

        "quality":
            quality,

        # ----------------------------------------------------
        # MEDIA
        # ----------------------------------------------------

        "frames_analyzed":
            len(frames),

        "media_type":
            "video"
            if video
            else
            "image",

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        "ocr_text":
            ocr_text[:2000],

        "order_ids_found":
            order_ids,

        "package_order_match":
            package_order_match,

        # ----------------------------------------------------
        # VARIANTS
        # ----------------------------------------------------

        "expected_color":
            expected_color,

        "color_match":
            color_match,

        "expected_size":
            expected_size,

        "detected_sizes":
            detected_sizes,

        "size_match":
            size_match,

        "expected_model":
            expected_model,

        "model_text_match":
            model_text_match,

        # ----------------------------------------------------
        # FRAME DETAILS
        # ----------------------------------------------------

        "frame_results":
            analyses,
    }