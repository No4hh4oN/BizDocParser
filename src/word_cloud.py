from __future__ import annotations


CLOUD_COLORS = ["#2563a8", "#0f766e", "#c65f19", "#b4233c", "#5b55a3"]


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
