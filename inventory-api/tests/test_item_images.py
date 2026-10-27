from io import BytesIO

import pytest
from PIL import Image

from app.services.item_images import (
    InvalidImageError,
    MAX_IMAGE_BYTES,
    delete_stored_image,
    resolve_stored_image,
    store_item_image,
)


def make_image(image_format):
    output = BytesIO()
    Image.new("RGB", (10, 8), (20, 80, 140)).save(output, format=image_format)
    return output.getvalue()


@pytest.mark.parametrize(
    ("image_format", "extension", "media_type"),
    [
        ("JPEG", ".jpg", "image/jpeg"),
        ("PNG", ".png", "image/png"),
        ("WEBP", ".webp", "image/webp"),
        ("GIF", ".gif", "image/gif"),
    ],
)
def test_valid_image_is_decoded_and_stored_with_generated_basename(
    tmp_path, monkeypatch, image_format, extension, media_type
):
    monkeypatch.setenv("ITEM_IMAGE_DIR", str(tmp_path / "item-images"))

    filename, stored_media_type = store_item_image(make_image(image_format))
    image_path = resolve_stored_image(filename)

    assert filename.endswith(extension)
    assert "/" not in filename and "\\" not in filename
    assert stored_media_type == media_type
    assert image_path.is_file()
    with Image.open(image_path) as stored_image:
        stored_image.verify()

    delete_stored_image(filename)
    assert not image_path.exists()


@pytest.mark.parametrize(
    "contents",
    [b"not an image", b"", b"x" * (MAX_IMAGE_BYTES + 1)],
)
def test_invalid_or_oversized_image_is_rejected(tmp_path, monkeypatch, contents):
    monkeypatch.setenv("ITEM_IMAGE_DIR", str(tmp_path / "item-images"))

    with pytest.raises(InvalidImageError):
        store_item_image(contents)


def test_stored_image_resolver_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("ITEM_IMAGE_DIR", str(tmp_path / "item-images"))

    with pytest.raises(ValueError):
        resolve_stored_image("../outside.png")
