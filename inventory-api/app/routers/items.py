from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import ItemDB
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
