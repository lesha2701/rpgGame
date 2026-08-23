"""Admin image upload — local disk storage, served back via StaticFiles
(see main.py's app.mount). Architecturally the same shape as the football
app's own image_service.py (validate extension/content-type/size, sanitize
filename, write to a per-resource directory, return the DB-stored relative
path), not copied — trimmed to exactly the four resource kinds RPG actually
needs (heroes, enemies, items, expeditions) instead of football's much
longer list, and returns/deletes by directory+relative-path rather than by
a set of named per-entity functions.

This is deliberately NOT Stage 12's (design-only) AI artwork pipeline —
there is no status machine, no versioning, no provider abstraction here.
It's the same one-image-per-template model `image_path` already implied
since Stage 1; this just finally puts a real file behind it.

"chests" was added in a later pass alongside heroes/enemies/items/
expeditions — `Chest` already had an `image_path` column from Stage 5, it
just had no upload endpoint until now."""

import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import UploadFile

from app.core.exceptions import AppError

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"

ResourceKind = Literal["heroes", "enemies", "items", "expeditions", "chests", "app_icons"]

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

_SAFE_CHARS = re.compile(r"[^a-z0-9_-]+")


def _safe_stub(display_name: str) -> str:
    stub = display_name.strip().lower().replace(" ", "_")
    stub = _SAFE_CHARS.sub("", stub)
    return stub or "image"


async def save_template_image(upload: UploadFile, kind: ResourceKind, display_name: str) -> str:
    """Validates and stores an uploaded template image; returns the
    DB-stored relative path (e.g. "enemies/goblin_a1b2c3d4.png")."""
    if not upload.filename or "." not in upload.filename:
        raise AppError("invalid_file", "File has no extension", 400)

    extension = upload.filename.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AppError("invalid_file_type", f"Extension .{extension} is not allowed", 400)
    if upload.content_type and upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise AppError("invalid_file_type", f"Content-Type {upload.content_type} is not allowed", 400)

    contents = await upload.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise AppError("file_too_large", f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit", 400)
    if len(contents) == 0:
        raise AppError("invalid_file", "Uploaded file is empty", 400)

    target_dir = STATIC_DIR / kind
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_safe_stub(display_name)}_{uuid.uuid4().hex[:8]}.{extension}"
    (target_dir / filename).write_bytes(contents)

    return f"{kind}/{filename}"


def delete_template_image(relative_path: str | None) -> None:
    """Best-effort cleanup of the file an image_path column is about to
    stop pointing at (a replacement upload, or the row itself being
    edited) — never raises if the file is already gone, and refuses to
    touch anything outside STATIC_DIR."""
    if not relative_path:
        return
    full_path = (STATIC_DIR / relative_path).resolve()
    if STATIC_DIR.resolve() in full_path.parents and full_path.is_file():
        full_path.unlink(missing_ok=True)
