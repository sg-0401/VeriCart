"""
VeriCart AI-generated media detector.

Detects whether submitted images appear:
- Real
- AI-generated
- Uncertain

Videos are handled by analysing the sampled frames produced
by VeriCart's existing video-processing pipeline.
"""

from __future__ import annotations

import io
from functools import lru_cache

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification


MODEL_ID = "Smogy/SMOGY-Ai-images-detector"


@lru_cache(maxsize=1)
def _load_model():
    """
    Load the AI detector once and cache it.

    Loading the model repeatedly for every uploaded image would
    be unnecessarily slow.
    """

    processor = AutoImageProcessor.from_pretrained(MODEL_ID)

    model = AutoModelForImageClassification.from_pretrained(
        MODEL_ID
    )

    model.eval()

    return processor, model


def _image_from_bytes(image_bytes: bytes) -> Image.Image:
    """Convert uploaded image bytes into RGB PIL image."""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        return image.convert("RGB")

    except Exception as exc:
        raise ValueError(
            "The uploaded image could not be decoded for AI detection."
        ) from exc


def _get_label_map(model):
    """
    Obtain the model's actual label mapping.

    We do not hard-code class numbers because different models
    can use different label ordering.
    """

    return {
        int(index): str(label).lower()
        for index, label in model.config.id2label.items()
    }


def detect_ai_image(image_bytes: bytes) -> dict:
    """
    Analyse a single image.

    Returns:
        ai_probability
        real_probability
        label
        status
        confidence
    """

    image = _image_from_bytes(image_bytes)

    processor, model = _load_model()

    inputs = processor(
        images=image,
        return_tensors="pt"
    )

    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.softmax(
        outputs.logits,
        dim=-1
    )[0]

    labels = _get_label_map(model)

    ai_probability = 0.0
    real_probability = 0.0

    for index, probability in enumerate(probabilities):

        label = labels.get(index, "")

        probability = float(probability)

        if any(
            word in label
            for word in (
                "ai",
                "fake",
                "synthetic",
                "generated",
                "artificial"
            )
        ):
            ai_probability += probability

        elif any(
            word in label
            for word in (
                "real",
                "authentic",
                "human"
            )
        ):
            real_probability += probability

    # Safety fallback.
    if ai_probability == 0.0 and real_probability == 0.0:

        top_index = int(
            torch.argmax(probabilities)
        )

        top_probability = float(
            probabilities[top_index]
        )

        top_label = labels.get(
            top_index,
            ""
        )

        if any(
            word in top_label
            for word in (
                "ai",
                "fake",
                "synthetic",
                "generated",
                "artificial"
            )
        ):
            ai_probability = top_probability
            real_probability = 1.0 - top_probability

        else:
            real_probability = top_probability
            ai_probability = 1.0 - top_probability

    # Keep values numerically safe.
    ai_probability = max(
        0.0,
        min(1.0, ai_probability)
    )

    real_probability = max(
        0.0,
        min(1.0, real_probability)
    )

    # Classification thresholds.
    if ai_probability >= 0.75:

        label = "ai_suspected"
        status = "suspicious"

    elif ai_probability >= 0.45:

        label = "uncertain"
        status = "uncertain"

    else:

        label = "likely_real"
        status = "likely_real"

    confidence = max(
        ai_probability,
        real_probability
    )

    return {
        "ai_probability": round(
            ai_probability,
            4
        ),

        "real_probability": round(
            real_probability,
            4
        ),

        "label": label,

        "status": status,

        "confidence": round(
            confidence,
            4
        ),

        "model": MODEL_ID,
    }


def detect_ai_video(frames: list[bytes]) -> dict:
    """
    Analyse a video using the frames already extracted by VeriCart.

    Each sampled frame is analysed independently.

    The final video score combines:
        - average AI probability
        - strongest suspicious frame
    """

    if not frames:

        raise ValueError(
            "No video frames were available for AI detection."
        )

    frame_results = []

    for index, frame in enumerate(frames):

        try:

            result = detect_ai_image(frame)

            frame_results.append({
                "frame": index + 1,
                **result
            })

        except Exception as exc:

            frame_results.append({
                "frame": index + 1,
                "error": str(exc)
            })

    valid_results = [
        result
        for result in frame_results
        if "ai_probability" in result
    ]

    if not valid_results:

        raise ValueError(
            "None of the video frames could be analysed for AI detection."
        )

    ai_probabilities = [
        result["ai_probability"]
        for result in valid_results
    ]

    mean_ai_probability = (
        sum(ai_probabilities)
        / len(ai_probabilities)
    )

    max_ai_probability = max(
        ai_probabilities
    )

    # Average is the main signal.
    # Maximum captures a particularly suspicious frame.
    video_ai_probability = (
        mean_ai_probability * 0.75
        + max_ai_probability * 0.25
    )

    if video_ai_probability >= 0.75:

        label = "ai_suspected"
        status = "suspicious"

    elif video_ai_probability >= 0.45:

        label = "uncertain"
        status = "uncertain"

    else:

        label = "likely_real"
        status = "likely_real"

    return {
        "ai_probability": round(
            video_ai_probability,
            4
        ),

        "real_probability": round(
            1.0 - video_ai_probability,
            4
        ),

        "label": label,

        "status": status,

        "confidence": round(
            max(
                video_ai_probability,
                1.0 - video_ai_probability
            ),
            4
        ),

        "frames_analyzed": len(
            valid_results
        ),

        "frame_results": frame_results,

        "model": MODEL_ID,
    }