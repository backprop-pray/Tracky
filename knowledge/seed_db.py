from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psycopg


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
RECOMMENDATION_LIMIT = 60
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT_DIR / "init_data"

CURATED_RECOMMENDATIONS = {
    "anthracnose": "Prune infected fruit, keep leaves dry, spray copper.",
    "botrytis": "Remove infected tissue, ventilate well, avoid wet leaves.",
    "corn common rust": "Use resistant hybrids; spray only at high rust pressure.",
    "corn northern corn leaf blight": "Plant resistant hybrids, rotate crops, spray when needed.",
    "mildew": "Prune infected leaves, boost airflow, spray sulfur early.",
    "potato early bligh": "Scout weekly, rotate crops, mulch soil, rotate fungicides.",
    "potato early blight": "Scout weekly, rotate crops, mulch soil, rotate fungicides.",
    "tomato late blight": "Rotate 3y, drip in mornings, remove infected plants fast.",
    "wilt": "Water at dawn, add shade, and trim heat-damaged growth.",
}


@dataclass
class SeedEntry:
    file_name: str
    image_path: Path
    latitude: float | None
    longitude: float | None
    user_id: int | None
    plant_id: int | None
    image_url: str | None


@dataclass
class SeedGroup:
    disease: str
    notes: str
    recommendation: str
    entries: list[SeedEntry]


def load_env_files() -> None:
    candidates = [ROOT_DIR / ".env", ROOT_DIR.parent / ".env"]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def slugify(value: str) -> str:
    lowered = value.lower().replace("—", "-").replace("_", "-")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "seed"


def normalize_disease_key(value: str) -> str:
    lowered = value.lower().replace("—", " ").replace("_", " ")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def smart_title(value: str) -> str:
    parts = re.split(r"[-_\s]+", value.strip())
    titled = []
    for part in parts:
        if part.isupper() and len(part) <= 4:
            titled.append(part)
        else:
            titled.append(part.capitalize())
    return " ".join(filter(None, titled))


def read_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text().strip()


def trim_with_limit(text: str, limit: int = RECOMMENDATION_LIMIT) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return "Inspect symptoms closely and treat early to limit spread."
    if len(cleaned) <= limit:
        return cleaned.rstrip(".,;: ") + "."

    cut = cleaned[:limit].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;: ") + "."


def summarize_notes(notes: str) -> str:
    normalized = re.sub(r"\s+", " ", notes.strip())
    if not normalized:
        return "Inspect symptoms closely and treat early to limit spread."

    chunks = re.split(r"[.;]\s+|\n+", normalized)
    best = chunks[0].strip() if chunks else normalized
    best = best.lstrip("-0123456789. ")
    return trim_with_limit(best)


def recommendation_for(disease: str, notes: str, explicit: str) -> str:
    if explicit.strip():
        return trim_with_limit(explicit)
    curated = CURATED_RECOMMENDATIONS.get(normalize_disease_key(disease))
    if curated:
        return curated
    return summarize_notes(notes)


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return float(cleaned)


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return int(cleaned)


def load_entries_csv(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            file_name = (row.get("file") or "").strip()
            if not file_name:
                continue
            rows[file_name] = row
        return rows


def build_entries(images_dir: Path, entry_rows: dict[str, dict[str, str]]) -> list[SeedEntry]:
    image_paths = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    entries: list[SeedEntry] = []
    for image_path in image_paths:
        row = entry_rows.get(image_path.name, {})
        entries.append(
            SeedEntry(
                file_name=image_path.name,
                image_path=image_path,
                latitude=parse_float(row.get("latitude")),
                longitude=parse_float(row.get("longitude")),
                user_id=parse_int(row.get("user_id")),
                plant_id=parse_int(row.get("plant_id")),
                image_url=(row.get("image_url") or "").strip() or None,
            )
        )
    return entries


def discover_seed_groups(data_dir: Path) -> list[SeedGroup]:
    groups: list[SeedGroup] = []
    for entry in sorted(data_dir.iterdir()):
        if not entry.is_dir():
            continue

        disease = read_text_file(entry / "disease.txt") or smart_title(entry.name)
        notes = read_text_file(entry / "notes.txt")
        explicit_recommendation = read_text_file(entry / "recommendation.txt")
        entries = build_entries(entry / "images", load_entries_csv(entry / "entries.csv"))
        if not entries:
            continue

        groups.append(
            SeedGroup(
                disease=disease,
                notes=notes,
                recommendation=recommendation_for(disease, notes, explicit_recommendation),
                entries=entries,
            )
        )
    return groups


def parse_db_settings() -> dict[str, str | int]:
    spring_url = os.getenv("SPRING_DATASOURCE_URL", "").strip()
    if spring_url.startswith("jdbc:"):
        spring_url = spring_url[5:]
    parsed = urlparse(spring_url)
    if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.path:
        raise RuntimeError("Missing SPRING_DATASOURCE_URL for Postgres connection.")

    user = os.getenv("SPRING_DATASOURCE_USERNAME", "").strip()
    password = os.getenv("SPRING_DATASOURCE_PASSWORD", "").strip()
    if not user or not password:
        raise RuntimeError("Missing SPRING_DATASOURCE_USERNAME or SPRING_DATASOURCE_PASSWORD.")

    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/"),
        "user": user,
        "password": password,
    }


def open_db_connection() -> psycopg.Connection:
    settings = parse_db_settings()
    return psycopg.connect(
        host=settings["host"],
        port=settings["port"],
        dbname=settings["dbname"],
        user=settings["user"],
        password=settings["password"],
    )


def require_cloudinary_settings() -> tuple[str, str, str]:
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError("Missing Cloudinary credentials in environment.")
    return cloud_name, api_key, api_secret


def upload_image_to_cloudinary(image_path: Path, disease_slug: str) -> str:
    cloud_name, api_key, api_secret = require_cloudinary_settings()
    timestamp = int(time.time())
    folder = f"Plants/knowledge-seed/{disease_slug}"
    public_id = slugify(image_path.stem)

    signature_base = f"folder={folder}&overwrite=true&public_id={public_id}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(signature_base.encode("utf-8")).hexdigest()
    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

    with image_path.open("rb") as image_file:
        files = {"file": (image_path.name, image_file, "application/octet-stream")}
        data = {
            "api_key": api_key,
            "folder": folder,
            "overwrite": "true",
            "public_id": public_id,
            "timestamp": str(timestamp),
            "signature": signature,
        }
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.post(upload_url, data=data, files=files)
            response.raise_for_status()
            payload = response.json()

    final_url = payload.get("url") or payload.get("secure_url")
    if not final_url:
        raise RuntimeError(f"Cloudinary upload returned no URL for {image_path}")
    return final_url


def resolve_image_url(entry: SeedEntry, disease_slug: str) -> str:
    if entry.image_url:
        return entry.image_url
    return upload_image_to_cloudinary(entry.image_path, disease_slug)


def ensure_plant(
    conn: psycopg.Connection,
    entry: SeedEntry,
    image_url: str,
    latitude: float,
    longitude: float,
    user_id: int,
) -> int:
    with conn.cursor() as cur:
        if entry.plant_id is not None:
            cur.execute(
                "UPDATE public.plants SET latitude = %s, longitude = %s, image_url = %s, user_id = %s, status = %s WHERE id = %s",
                (latitude, longitude, image_url, user_id, None, entry.plant_id),
            )
            return entry.plant_id

        cur.execute("SELECT id FROM public.plants WHERE image_url = %s ORDER BY id DESC LIMIT 1", (image_url,))
        row = cur.fetchone()
        if row:
            plant_id = int(row[0])
            cur.execute(
                "UPDATE public.plants SET latitude = %s, longitude = %s, user_id = %s, status = %s WHERE id = %s",
                (latitude, longitude, user_id, None, plant_id),
            )
            return plant_id

        cur.execute(
            "INSERT INTO public.plants (latitude, longitude, image_url, user_id, status, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING id",
            (latitude, longitude, image_url, user_id, None),
        )
        inserted = cur.fetchone()
        if not inserted:
            raise RuntimeError(f"Failed to create plant for {image_url}")
        return int(inserted[0])


def upsert_processed_plant(
    conn: psycopg.Connection,
    plant_id: int,
    disease: str,
    recommendation: str,
    user_id: int,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM public.processed_plants WHERE plant_id = %s ORDER BY id DESC LIMIT 1",
            (plant_id,),
        )
        row = cur.fetchone()
        if row:
            processed_id = int(row[0])
            cur.execute(
                "UPDATE public.processed_plants "
                "SET disease = %s, recommended_action = %s, status = %s, recommended_action_user_id = %s "
                "WHERE id = %s",
                (disease, recommendation, None, user_id, processed_id),
            )
            return processed_id

        cur.execute(
            "INSERT INTO public.processed_plants "
            "(plant_id, disease, recommended_action, status, recommended_action_user_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING id",
            (plant_id, disease, recommendation, None, user_id),
        )
        inserted = cur.fetchone()
        if not inserted:
            raise RuntimeError(f"Failed to create processed plant for plant {plant_id}")
        return int(inserted[0])


def canonicalize_recommendation_by_disease(
    conn: psycopg.Connection,
    disease: str,
    recommendation: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.processed_plants SET recommended_action = %s WHERE disease = %s",
            (recommendation, disease),
        )


def assign_missing_coordinates(
    groups: list[SeedGroup],
    base_latitude: float | None,
    base_longitude: float | None,
    lat_step: float,
    lon_step: float,
) -> list[tuple[SeedGroup, SeedEntry, float | None, float | None]]:
    assignments: list[tuple[SeedGroup, SeedEntry, float | None, float | None]] = []
    offset = 0
    for group in groups:
        for entry in group.entries:
            latitude = entry.latitude
            longitude = entry.longitude
            if latitude is None and base_latitude is not None:
                latitude = base_latitude + (offset * lat_step)
            if longitude is None and base_longitude is not None:
                longitude = base_longitude + (offset * lon_step)
            assignments.append((group, entry, latitude, longitude))
            offset += 1
    return assignments


def is_entry_seedable(
    entry: SeedEntry,
    resolved_user_id: int | None,
    latitude: float | None,
    longitude: float | None,
) -> bool:
    return resolved_user_id is not None and latitude is not None and longitude is not None


def run_seed(
    data_dir: Path,
    user_id: int | None,
    base_latitude: float | None,
    base_longitude: float | None,
    lat_step: float,
    lon_step: float,
    dry_run: bool,
) -> None:
    groups = discover_seed_groups(data_dir)
    if not groups:
        raise RuntimeError(f"No seed groups found in {data_dir}")

    assignments = assign_missing_coordinates(groups, base_latitude, base_longitude, lat_step, lon_step)

    print(f"Discovered {len(groups)} disease groups in {data_dir}")
    for group in groups:
        print(f"- {group.disease}: {len(group.entries)} image(s) -> {group.recommendation}")

    for group, entry, latitude, longitude in assignments:
        resolved_user_id = entry.user_id if entry.user_id is not None else user_id
        if dry_run:
            print(
                f"DRY RUN | {group.disease} | {entry.file_name} | "
                f"plant_id={entry.plant_id or ''} user={resolved_user_id or ''} | "
                f"lat={'' if latitude is None else f'{latitude:.6f}'} "
                f"lon={'' if longitude is None else f'{longitude:.6f}'}"
            )
            continue

        if not is_entry_seedable(entry, resolved_user_id, latitude, longitude):
            print(
                f"SKIP | {group.disease} | {entry.file_name} | "
                "missing user_id or coordinates"
            )
            continue

        assert resolved_user_id is not None
        assert latitude is not None
        assert longitude is not None

        disease_slug = slugify(group.disease)
        image_url = resolve_image_url(entry, disease_slug)
        with open_db_connection() as conn:
            plant_id = ensure_plant(conn, entry, image_url, latitude, longitude, resolved_user_id)
            processed_id = upsert_processed_plant(conn, plant_id, group.disease, group.recommendation, resolved_user_id)
            canonicalize_recommendation_by_disease(conn, group.disease, group.recommendation)
            conn.commit()
        print(
            f"SEEDED | processed={processed_id} plant={plant_id} | "
            f"{group.disease} | {entry.file_name}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed plants and processed_plants from knowledge/init_data")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--base-latitude", type=float)
    parser.add_argument("--base-longitude", type=float)
    parser.add_argument("--lat-step", type=float, default=0.0007)
    parser.add_argument("--lon-step", type=float, default=0.0009)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    load_env_files()
    args = build_parser().parse_args()
    run_seed(
        data_dir=args.data_dir.resolve(),
        user_id=args.user_id,
        base_latitude=args.base_latitude,
        base_longitude=args.base_longitude,
        lat_step=args.lat_step,
        lon_step=args.lon_step,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
