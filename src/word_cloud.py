from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from wordcloud import WordCloud


CLOUD_COLORS = ["#2563a8", "#0f766e", "#c65f19", "#b4233c", "#5b55a3"]
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\malgun.ttf"),
    Path(r"C:\Windows\Fonts\malgunbd.ttf"),
]


def build_word_cloud(top_words: list[dict[str, object]], max_words: int = 35) -> list[dict[str, object]]:
    cloud: list[dict[str, object]] = []
    for index, item in enumerate(top_words[:max_words]):
        weight = float(item.get("weight") or 0)
        cloud.append(
            {
                "word": item.get("word", ""),
                "count": item.get("count", 0),
                "weight": weight,
                "sizeRem": round(0.9 + weight * 1.65, 2),
                "color": CLOUD_COLORS[index % len(CLOUD_COLORS)],
            }
        )
    return cloud


def font_path() -> str | None:
    for path in FONT_CANDIDATES:
        if path.exists():
            return str(path)
    return None


def load_mask(mask_path: str | None = None) -> np.ndarray | None:
    if not mask_path:
        return None

    path = Path(mask_path)
    if not path.exists():
        return None
    return np.array(Image.open(path))


def build_word_cloud_image(
    top_words: list[dict[str, object]],
    mask_path: str | None = None,
    max_words: int = 2000,
) -> str:
    frequencies = {
        str(item.get("word", "")).strip(): int(item.get("count") or 0)
        for item in top_words
        if str(item.get("word", "")).strip() and int(item.get("count") or 0) > 0
    }
    if not frequencies:
        return ""

    wordcloud = WordCloud(
        background_color="white",
        max_words=max_words,
        font_path=font_path(),
        mask=load_mask(mask_path),
        random_state=42,
        width=1200,
        height=800,
        colormap="tab10",
    )
    wordcloud.generate_from_frequencies(frequencies)

    image = wordcloud.to_image()
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
