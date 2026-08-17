from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import ServerDB
from app.models import Server, ServerCreate, ServerUpdate


router = APIRouter(
    prefix="/servers",
    tags=["servers"],
)


@router.get("/", response_model=list[Server])
def get_servers(db: Session = Depends(get_db)):
    return db.query(ServerDB).all()

@router.get("/{server_id}", response_model=Server)
def get_server(
    server_id: int,
    db: Session = Depends(get_db),
):
    db_server = db.query(ServerDB).filter(
        ServerDB.id == server_id
    ).first()

    if db_server is None:
        raise HTTPException(
            status_code=404,
            detail="Server not found",
        )

    return db_server

@router.post("/", response_model=Server)
def create_server(
    server: ServerCreate,
    db: Session = Depends(get_db),
):
    db_server = ServerDB(
    name=server.name,
    ip=server.ip,
    environment=server.environment,
    status=server.status,
    location=server.location,
    )

    db.add(db_server)
    db.commit()
    db.refresh(db_server)

    return db_server

@router.put("/{server_id}", response_model=Server)
def update_server(
    server_id: int,
    server_data: ServerUpdate,
    db: Session = Depends(get_db),
):
    db_server = db.query(ServerDB).filter(
        ServerDB.id == server_id
    ).first()

    if db_server is None:
        raise HTTPException(
            status_code=404,
            detail="Server not found",
        )

    if server_data.name is not None:
        db_server.name = server_data.name

    if server_data.ip is not None:
        db_server.ip = server_data.ip

    if server_data.environment is not None:
        db_server.environment = server_data.environment

    if server_data.status is not None:
        db_server.status = server_data.status

    if server_data.location is not None:
        db_server.location = server_data.location

    db.commit()
    db.refresh(db_server)

    return db_server

@router.delete("/{server_id}")
def delete_server(
    server_id: int,
    db: Session = Depends(get_db),
):
    db_server = db.query(ServerDB).filter(
        ServerDB.id == server_id
    ).first()

    if db_server is None:
        raise HTTPException(
            status_code=404,
            detail="Server not found",
        )

    db.delete(db_server)
    db.commit()

    return {
        "message": "Server deleted successfully"
    }