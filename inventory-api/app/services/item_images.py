import os
import uuid
import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
    "GIF": ("gif", "image/gif"),
}


class InvalidImageError(ValueError):
    """Raised when an uploaded file is not a supported, valid raster image."""


def image_directory() -> Path:
    configured = os.getenv("ITEM_IMAGE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "uploads" / "items").resolve()


def store_item_image(data: bytes) -> tuple[str, str]:
    """Validate, decode and re-encode an image under a generated safe filename."""
    if not data:
        raise InvalidImageError("Image file is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidImageError("Image exceeds the 5 MiB limit")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                if image_format not in IMAGE_FORMATS:
                    raise InvalidImageError("Unsupported image format")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise InvalidImageError("Image dimensions are too large")
                image.verify()

            # Decode the content and write a fresh raster file so uploaded
            # metadata, trailing payloads, and client filenames are discarded.
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise InvalidImageError("Image dimensions are too large")
                image.seek(0)
                image.load()
                decoded_image = image.copy()
    except InvalidImageError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as error:
        raise InvalidImageError("Uploaded file is not a valid supported image") from error
    except Image.DecompressionBombWarning as error:
        raise InvalidImageError("Image dimensions are too large") from error

    extension, media_type = IMAGE_FORMATS[image_format]
    if image_format == "JPEG":
        decoded_image = decoded_image.convert("RGB")

    safe_name = f"{uuid.uuid4().hex}.{extension}"
    directory = image_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / safe_name
    created = False
    try:
        with target.open("xb") as output:
            created = True
            decoded_image.save(output, format=image_format, optimize=True)
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
    return safe_name, media_type


def resolve_stored_image(filename: str) -> Path:
    """Resolve only generated basenames below the configured image directory."""
    if not filename or Path(filename).name != filename:
        raise ValueError("Invalid stored image reference")
    path = (image_directory() / filename).resolve()
    if path.parent != image_directory():
        raise ValueError("Invalid stored image reference")
    return path


def media_type_for_image(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    try:
        return media_types[suffix]
    except KeyError as error:
        raise ValueError("Unsupported stored image reference") from error


def delete_stored_image(filename: str | None) -> None:
    if not filename:
        return
    path = resolve_stored_image(filename)
    path.unlink(missing_ok=True)
