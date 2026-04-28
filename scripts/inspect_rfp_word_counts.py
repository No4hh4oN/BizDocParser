from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from send_purchase_orders import extract_pdf_assets  # noqa: E402
from word_analyzer import tokenize_text  # noqa: E402


def main() -> None:
    pdf_paths = sorted((ROOT / "rfp_dummy_pdf").glob("*.pdf"))
    if not pdf_paths:
        raise RuntimeError("rfp_dummy_pdf 폴더에 PDF가 없습니다.")

    total_counter: Counter[str] = Counter()
    document_frequency: Counter[str] = Counter()

    for pdf_path in pdf_paths:
        assets = extract_pdf_assets(pdf_path)
        tokens = tokenize_text(str(assets.get("text", "")))
        counter = Counter(tokens)
        total_counter.update(counter)
        document_frequency.update(counter.keys())
        print(f"\n[{pdf_path.name}]")
        for word, count in counter.most_common(35):
            print(f"{word}\t{count}")

    print("\n[ALL TOP 120]")
    for word, count in total_counter.most_common(120):
        print(f"{word}\t{count}\tdf={document_frequency[word]}")


if __name__ == "__main__":
    main()
