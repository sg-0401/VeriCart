"""
VeriCart AI-generated media detector.

Detects whether submitted images appear:
- Real
- AI-generated
- Uncertain

Videos are analysed using the sampled frames produced
by VeriCart's existing video-processing pipeline.

AI-media threshold:
- Below 60%: Continue normal verification.
- 60% or above: Request an unboxing video.

Suspicious media is NOT automatically rejected.
"""

from __future__ import annotations

import io
from functools import lru_cache

import torch
from PIL import Image
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
)


MODEL_ID = "Smogy/SMOGY-Ai-images-detector"

AI_MEDIA_THRESHOLD = 0.60


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the AI detection model."""

    processor = AutoImageProcessor.from_pretrained(
        MODEL_ID
    )

    model = AutoModelForImageClassification.from_pretrained(
        MODEL_ID
    )

    model.eval()

    return processor, model


def _image_from_bytes(image_bytes: bytes) -> Image.Image:
    """Convert uploaded image bytes into RGB format."""

    try:
        image = Image.open(
            io.BytesIO(image_bytes)
        )

        return image.convert("RGB")

    except Exception as exc:
        raise ValueError(
            "The uploaded image could not be decoded "
            "for AI detection."
        ) from exc


def _get_label_map(model):
    """Read the model's actual class labels."""

    return {
        int(index): str(label).lower()
        for index, label in model.config.id2label.items()
    }


def _classify_probability(ai_probability: float):
    """
    Classify media using the 60% threshold.

    This classification is a verification warning,
    not an automatic rejection.
    """

    if ai_probability >= AI_MEDIA_THRESHOLD:

        return {
            "label": "ai_suspected",
            "status": "suspicious",
            "requires_unboxing_video": True,
        }

    return {
        "label": "likely_real",
        "status": "likely_real",
        "requires_unboxing_video": False,
    }


def detect_ai_image(image_bytes: bytes) -> dict:
    """
    Analyse a single image for AI-generated characteristics.

    Returns AI probability, real probability, confidence,
    classification and whether an unboxing video is required.
    """

    image = _image_from_bytes(
        image_bytes
    )

    processor, model = _load_model()

    inputs = processor(
        images=image,
        return_tensors="pt"
    )

    with torch.no_grad():

        outputs = model(
            **inputs
        )

    probabilities = torch.softmax(
        outputs.logits,
        dim=-1
    )[0]

    labels = _get_label_map(
        model
    )

    ai_probability = 0.0
    real_probability = 0.0

    for index, probability in enumerate(probabilities):

        class_label = labels.get(
            index,
            ""
        )

        probability = float(
            probability
        )

        if any(
            word in class_label
            for word in (
                "ai",
                "fake",
                "synthetic",
                "generated",
                "artificial",
            )
        ):

            ai_probability += probability

        elif any(
            word in class_label
            for word in (
                "real",
                "authentic",
                "human",
            )
        ):

            real_probability += probability

    # Fallback for models with unexpected class labels.
    if (
        ai_probability == 0.0
        and real_probability == 0.0
    ):

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
                "artificial",
            )
        ):

            ai_probability = top_probability

            real_probability = (
                1.0 - top_probability
            )

        else:

            real_probability = top_probability

            ai_probability = (
                1.0 - top_probability
            )

    # Keep probabilities within valid limits.
    ai_probability = max(
        0.0,
        min(1.0, ai_probability)
    )

    real_probability = max(
        0.0,
        min(1.0, real_probability)
    )

    classification = _classify_probability(
        ai_probability
    )

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

        "label": classification["label"],

        "status": classification["status"],

        "confidence": round(
            confidence,
            4
        ),

        "requires_unboxing_video":
            classification["requires_unboxing_video"],

        "threshold": AI_MEDIA_THRESHOLD,

        "model": MODEL_ID,
    }


def detect_ai_video(frames: list[bytes]) -> dict:
    """
    Analyse a video using its extracted frames.

    The final probability combines:
    - Average AI probability across frames.
    - Highest AI probability among the frames.

    A suspicious result requests further evidence.
    It does not automatically reject the return.
    """

    if not frames:

        raise ValueError(
            "No video frames were available "
            "for AI detection."
        )

    frame_results = []

    for index, frame in enumerate(frames):

        try:

            result = detect_ai_image(
                frame
            )

            frame_results.append({
                "frame": index + 1,
                **result,
            })

        except Exception as exc:

            frame_results.append({
                "frame": index + 1,
                "error": str(exc),
            })

    valid_results = [
        result
        for result in frame_results
        if "ai_probability" in result
    ]

    if not valid_results:

        raise ValueError(
            "None of the video frames could be "
            "analysed for AI detection."
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

    video_ai_probability = (
        mean_ai_probability * 0.75
        +
        max_ai_probability * 0.25
    )

    video_ai_probability = max(
        0.0,
        min(1.0, video_ai_probability)
    )

    classification = _classify_probability(
        video_ai_probability
    )

    real_probability = (
        1.0 - video_ai_probability
    )

    confidence = max(
        video_ai_probability,
        real_probability
    )

    return {
        "ai_probability": round(
            video_ai_probability,
            4
        ),

        "real_probability": round(
            real_probability,
            4
        ),

        "label": classification["label"],

        "status": classification["status"],

        "confidence": round(
            confidence,
            4
        ),

        "requires_unboxing_video":
            classification["requires_unboxing_video"],

        "threshold": AI_MEDIA_THRESHOLD,

        "frames_analyzed": len(
            valid_results
        ),

        "frame_results": frame_results,

        "model": MODEL_ID,
    }