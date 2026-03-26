from __future__ import annotations

from pathlib import Path

from PIL import Image

from openclip_rag import OpenClipRAGIndex


BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "test_images"


def print_hits(title: str, hits) -> None:
    print(f"\n=== {title} ===")
    for hit in hits:
        print(f"{hit.rank}. {hit.image_name:<20} score={hit.score:.4f}")


def run() -> None:
    rag = OpenClipRAGIndex(
        image_dir=IMAGE_DIR,
        model_name="ViT-B-32",
        pretrained="laion2b_s34b_b79k",
    )
    indexed = rag.build_index()
    print(f"Indexed images: {indexed}")

    text_queries = [
        "apple leaf with green bugs",
        "wheat disease on leaf",
        "corn leaf with infection",
        "healthy crop leaf",
        "plant disease close-up",
        "bugs eating green leaf",
    ]

    for query in text_queries:
        hits = rag.search_text(query, top_k=3)
        print_hits(f"TEXT: {query}", hits)

    image_files = sorted(p for p in IMAGE_DIR.iterdir() if p.is_file())
    for image_path in image_files:
        hits = rag.search_image_path(image_path, top_k=3)
        print_hits(f"IMAGE: {image_path.name}", hits)

    mixed_pairs = [
        ("green bugs on apple leaf", "Apple.png"),
        ("diseased wheat leaf", "Wheat.png"),
        ("crop disease spots", "Cron.png"),
        ("random disease on crop", "Apple.png"),
        ("insects on plant", "Cron.png"),
    ]

    for text_query, image_name in mixed_pairs:
        image_path = IMAGE_DIR / image_name
        with Image.open(image_path) as image:
            hits = rag.search_mixed(
                query_text=text_query,
                image=image,
                top_k=3,
                text_weight=0.6,
            )
        print_hits(f"MIXED: text='{text_query}' + image='{image_name}'", hits)


if __name__ == "__main__":
    run()
