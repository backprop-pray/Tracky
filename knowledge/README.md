# Knowledge OpenCLIP RAG

FastAPI microservice for multimodal retrieval over local plant images.

## What it does

- Loads images from `knowledge/test_images` into RAM.
- Encodes both text and images with OpenCLIP.
- Supports text-to-image, image-to-image, and mixed text+image search.
- Does not touch the database.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run service

```bash
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

Optional env vars:

- `KNOWLEDGE_IMAGE_DIR` (default: `knowledge/test_images`)
- `OPENCLIP_MODEL` (default: `ViT-B-32`)
- `OPENCLIP_PRETRAINED` (default: `laion2b_s34b_b79k`)

## API quick checks

```bash
curl http://127.0.0.1:8001/health
curl -X POST http://127.0.0.1:8001/search/text -H "Content-Type: application/json" -d '{"query":"apple leaf with green bugs","top_k":3}'
curl -X POST http://127.0.0.1:8001/search/image -F "image=@test_images/Apple.png" -F "top_k=3"
curl -X POST http://127.0.0.1:8001/search/mixed -F "query=green bugs on apple leaf" -F "image=@test_images/Apple.png" -F "top_k=3" -F "text_weight=0.6"
```

## Permutation test runner

```bash
python test_permutations.py
```

This runs text, image, and mixed queries and prints top matches.
