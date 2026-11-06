import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


TEST_DATABASE_HOST = "127.0.0.1"
TEST_DATABASE_PORT = 15432
TEST_DATABASE_NAME = "inventory_test"


def _validated_test_database_url():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail(
            "TEST_DATABASE_URL es obligatorio para estos tests.", pytrace=False
        )

    try:
        url = make_url(database_url)
    except Exception:
        pytest.fail("TEST_DATABASE_URL no es una URL válida.", pytrace=False)

    if url.drivername != "postgresql+psycopg":
        pytest.fail(
            "TEST_DATABASE_URL debe usar postgresql+psycopg.", pytrace=False
        )
    if url.host != TEST_DATABASE_HOST:
        pytest.fail(
            f"El host de pruebas debe ser {TEST_DATABASE_HOST}.", pytrace=False
        )
    if url.port != TEST_DATABASE_PORT:
        pytest.fail(
            f"El puerto de pruebas debe ser {TEST_DATABASE_PORT}.", pytrace=False
        )
    if url.database != TEST_DATABASE_NAME:
        pytest.fail(
            f"La base de pruebas debe llamarse exactamente {TEST_DATABASE_NAME}.",
            pytrace=False,
        )
    if url.query:
        pytest.fail(
            "TEST_DATABASE_URL no admite parámetros adicionales.", pytrace=False
        )

    return database_url


@pytest.fixture
def client():
    database_url = _validated_test_database_url()
    engine = create_engine(database_url)

    try:
        with engine.connect() as connection:
            actual_database = connection.scalar(text("SELECT current_database()"))
            if actual_database != TEST_DATABASE_NAME:
                pytest.fail(
                    "La conexión llegó a una base distinta de la base de pruebas; "
                    "no se modificó el esquema.",
                    pytrace=False,
                )
    except pytest.fail.Exception:
        engine.dispose()
        raise
    except Exception:
        engine.dispose()
        pytest.fail("No se pudo verificar la base de datos de pruebas.", pytrace=False)

    overrides = app.dependency_overrides
    previous_overrides = overrides.copy()
    try:
        TestingSessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
        )

        def override_get_db():
            db = TestingSessionLocal()

            try:
                yield db
            finally:
                db.close()

        overrides[get_db] = override_get_db

        try:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
        except Exception:
            pytest.fail(
                "No se pudo preparar el esquema de la base de pruebas.",
                pytrace=False,
            )

        with TestClient(app) as test_client:
            yield test_client
    finally:
        try:
            overrides.clear()
            overrides.update(previous_overrides)
            app.dependency_overrides = overrides
        finally:
            engine.dispose()
