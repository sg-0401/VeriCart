from pathlib import Path

from utils.ai_media_detector import detect_ai_image


image_path = Path("images/Ajanta wallclock.jpg")

image_bytes = image_path.read_bytes()

result = detect_ai_image(image_bytes)

print("\n" + "=" * 60)
print("VERICART AI IMAGE DETECTION TEST")
print("=" * 60)

for key, value in result.items():
    print(f"{key}: {value}")

print("=" * 60)