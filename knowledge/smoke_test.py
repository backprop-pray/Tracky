from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import app


BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "test_images"


def run() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        print("/health", health.status_code, health.json())

        text_query = {"query": "apple leaf with green bugs", "top_k": 3}
        text_resp = client.post("/search/text", json=text_query)
        print("/search/text", text_resp.status_code, text_resp.json())

        image_path = IMAGE_DIR / "Apple.png"
        with image_path.open("rb") as f:
            image_resp = client.post(
                "/search/image",
                files={"image": ("Apple.png", f, "image/png")},
                data={"top_k": "3"},
            )
        print("/search/image", image_resp.status_code, image_resp.json())

        with image_path.open("rb") as f:
            mixed_resp = client.post(
                "/search/mixed",
                data={"query": "green bugs on apple leaf", "top_k": "3", "text_weight": "0.6"},
                files={"image": ("Apple.png", f, "image/png")},
            )
        print("/search/mixed", mixed_resp.status_code, mixed_resp.json())


if __name__ == "__main__":
    run()
