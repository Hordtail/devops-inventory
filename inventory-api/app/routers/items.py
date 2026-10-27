from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import ItemDB, StockMovementDB
from app.models import (
    Item,
    ItemCreate,
    ItemUpdate,
    StockMovement,
    StockMovementCreate,
)
from app.services.stock import (
    InactiveItemError,
    InsufficientStockError,
    InvalidMovementQuantityError,
    InvalidMovementTypeError,
    ItemNotFoundError,
    register_stock_movement,
)
from app.services.item_images import (
    MAX_IMAGE_BYTES,
    InvalidImageError,
    delete_stored_image,
    media_type_for_image,
    resolve_stored_image,
    store_item_image,
)


router = APIRouter(
    prefix="/items",
    tags=["items"],
)


@router.get("/", response_model=list[Item])
def get_items(db: Session = Depends(get_db)):
    return db.query(ItemDB).order_by(ItemDB.id).all()


@router.get("/{item_id}", response_model=Item)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()

    if db_item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    return db_item


@router.put("/{item_id}", response_model=Item)
def update_item(
    item_id: int,
    item_data: ItemUpdate,
    db: Session = Depends(get_db),
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()

    if db_item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    db_item.code = item_data.code
    db_item.name = item_data.name
    db_item.unit = item_data.unit
    db_item.active = item_data.active
    if "description" in item_data.model_fields_set:
        db_item.description = item_data.description
    if item_data.minimum_stock is not None:
        db_item.minimum_stock = item_data.minimum_stock

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        existing_item = (
            db.query(ItemDB)
            .filter(ItemDB.code == item_data.code, ItemDB.id != item_id)
            .first()
        )
        if existing_item is not None:
            raise HTTPException(
                status_code=409,
                detail="Item code already exists",
            ) from None

        raise HTTPException(
            status_code=500,
            detail="Unable to update item",
        ) from None

    db.refresh(db_item)
    return db_item


@router.patch("/{item_id}/deactivate", response_model=Item)
def deactivate_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()

    if db_item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    db_item.active = False
    db.commit()
    db.refresh(db_item)
    return db_item


@router.post("/", response_model=Item)
def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
):
    db_item = ItemDB(
        code=item.code,
        name=item.name,
        unit=item.unit,
        active=item.active,
        minimum_stock=item.minimum_stock,
        description=item.description,
    )

    db.add(db_item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        existing_item = db.query(ItemDB).filter(ItemDB.code == item.code).first()
        if existing_item is not None:
            raise HTTPException(
                status_code=409,
                detail="Item code already exists",
            ) from None

        raise HTTPException(
            status_code=500,
            detail="Unable to create item",
        ) from None

    db.refresh(db_item)
    return db_item


@router.get(
    "/{item_id}/movements",
    response_model=list[StockMovement],
)
def get_item_movements(
    item_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    item_exists = db.query(ItemDB.id).filter(ItemDB.id == item_id).first()
    if item_exists is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return (
        db.query(StockMovementDB)
        .filter(StockMovementDB.item_id == item_id)
        .order_by(desc(StockMovementDB.occurred_at), desc(StockMovementDB.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{item_id}/image")
def get_item_image(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if not db_item.image_path:
        raise HTTPException(status_code=404, detail="Item has no image")

    try:
        image_path = resolve_stored_image(db_item.image_path)
        media_type = media_type_for_image(db_item.image_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="Image not found") from None

    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type=media_type)


@router.post("/{item_id}/image", response_model=Item)
def upload_item_image(
    item_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        image_data = image.file.read(MAX_IMAGE_BYTES + 1)
        if len(image_data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 5 MiB limit",
            )
        try:
            image_reference, _media_type = store_item_image(image_data)
        except InvalidImageError as error:
            status_code = (
                413
                if "exceeds" in str(error).lower()
                or "too large" in str(error).lower()
                else 415
            )
            raise HTTPException(status_code=status_code, detail=str(error)) from error

        old_image_reference = db_item.image_path
        db_item.image_path = image_reference
        try:
            db.commit()
        except Exception:
            db.rollback()
            delete_stored_image(image_reference)
            raise HTTPException(
                status_code=500,
                detail="Unable to save item image",
            ) from None

        db.refresh(db_item)
        if old_image_reference and old_image_reference != image_reference:
            delete_stored_image(old_image_reference)
        return db_item
    finally:
        image.file.close()


def _register_movement_response(
    db: Session,
    item_id: int,
    movement_type: str,
    movement_data: StockMovementCreate,
) -> StockMovement:
    """Map stock domain errors to API errors without querying before service."""
    try:
        return register_stock_movement(
            db,
            item_id,
            movement_type,
            movement_data.quantity,
            movement_data.note,
        )
    except ItemNotFoundError as error:
        raise HTTPException(status_code=404, detail="Item not found") from error
    except (InactiveItemError, InsufficientStockError) as error:
        # Resource state conflicts use 409; malformed movement input uses 422.
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except (InvalidMovementQuantityError, InvalidMovementTypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/{item_id}/movements/in", response_model=StockMovement)
def register_stock_in(
    item_id: int,
    movement_data: StockMovementCreate,
    db: Session = Depends(get_db),
):
    """Register stock received for an item."""
    return _register_movement_response(db, item_id, "IN", movement_data)


@router.post("/{item_id}/movements/out", response_model=StockMovement)
def register_stock_out(
    item_id: int,
    movement_data: StockMovementCreate,
    db: Session = Depends(get_db),
):
    """Register stock consumed for an item."""
    return _register_movement_response(db, item_id, "OUT", movement_data)
