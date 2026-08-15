from fastapi import APIRouter, HTTPException

from app.models import Server, ServerCreate, ServerUpdate


router = APIRouter(
    prefix="/servers",
    tags=["servers"],
)


servers: list[Server] = [
    Server(
        id=1,
        name="web-01",
        ip="192.168.1.10",
        environment="production",
        status="running",
    ),
    Server(
        id=2,
        name="db-01",
        ip="192.168.1.20",
        environment="production",
        status="running",
    ),
]


@router.get("/", response_model=list[Server])
def get_servers():
    return servers


@router.get("/{server_id}", response_model=Server)
def get_server(server_id: int):
    for server in servers:
        if server.id == server_id:
            return server

    raise HTTPException(
        status_code=404,
        detail="Server not found",
    )


@router.post("/", response_model=Server, status_code=201)
def create_server(server_data: ServerCreate):
    new_id = max((server.id for server in servers), default=0) + 1

    new_server = Server(
        id=new_id,
        **server_data.model_dump(),
    )

    servers.append(new_server)

    return new_server


@router.put("/{server_id}", response_model=Server)
def update_server(server_id: int, server_data: ServerUpdate):
    for index, server in enumerate(servers):
        if server.id == server_id:
            updated_server = Server(
                id=server_id,
                **server_data.model_dump(),
            )

            servers[index] = updated_server

            return updated_server

    raise HTTPException(
        status_code=404,
        detail="Server not found",
    )


@router.delete("/{server_id}", status_code=204)
def delete_server(server_id: int):
    for index, server in enumerate(servers):
        if server.id == server_id:
            servers.pop(index)
            return

    raise HTTPException(
        status_code=404,
        detail="Server not found",
    )