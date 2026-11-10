"""Image file lifecycle: Supabase Cloud Storage with local disk temporary pipeline.

Image files are processed locally during upload and then pushed to Supabase Storage.
The database stores the public cloud URLs (or local paths as fallback).

Cleanup mechanisms:
  * delete_image_files(image) — removes the object(s) from Supabase or disk when
    a report is finalized.
  * sweep_expired() — backstop for temporary local files older than
    IMAGE_RETENTION_HOURS.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy / conditional Supabase client initialization
supabase: Client | None = None
if settings.supabase_url and settings.supabase_key:
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_key)
    except Exception as exc:
        logger.warning("Failed to initialize Supabase client: %s", exc)


def upload_to_supabase(local_path: Path, remote_filename: str, content_type: str) -> str:
    """Upload a local file to Supabase Storage and return its public URL."""
    if not supabase:
        raise RuntimeError("Supabase client is not configured.")

    with open(local_path, "rb") as f:
        supabase.storage.from_(settings.supabase_bucket).upload(
            file=f,
            path=remote_filename,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    return supabase.storage.from_(settings.supabase_bucket).get_public_url(remote_filename)


def delete(path_str: str | None) -> None:
    """Best-effort removal of one local file; never raises (cleanup must not mask errors)."""
    if not path_str:
        return
    try:
        Path(path_str).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete local file: %s", path_str)


def delete_image_files(image) -> None:
    """Remove an Image row's files from Supabase Storage or local disk."""
    if not image.stored_path:
        return

    if image.stored_path.startswith(("http://", "https://")) and supabase:
        paths_to_delete = []
        for path_attr in (image.stored_path, getattr(image, "processed_path", None)):
            if path_attr and path_attr.startswith(("http://", "https://")):
                parts = path_attr.split(f"/{settings.supabase_bucket}/")
                if len(parts) > 1:
                    rel_path = parts[1].split("?")[0]
                    paths_to_delete.append(rel_path)

        if paths_to_delete:
            try:
                supabase.storage.from_(settings.supabase_bucket).remove(paths_to_delete)
            except Exception as exc:
                logger.warning("Could not delete files %s from Supabase: %s", paths_to_delete, exc)
        return

    # Local storage fallback deletion
    delete(image.stored_path)
    delete(image.processed_path)


def sweep_expired() -> int:
    """Delete local temporary image files older than IMAGE_RETENTION_HOURS."""
    if settings.image_retention_hours <= 0:
        return 0

    cutoff = time.time() - settings.image_retention_hours * 3600
    removed = 0
    for directory in (settings.upload_path, settings.processed_path):
        if not directory.is_dir():
            continue
        for f in directory.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:  
                continue
    if removed:
        logger.info("Retention sweep removed %d expired image file(s).", removed)
    return removed