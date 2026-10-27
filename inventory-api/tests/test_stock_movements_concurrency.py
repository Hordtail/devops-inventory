"""PostgreSQL integration test for concurrent stock movements.

This test requires a dedicated, already-migrated database. It intentionally
does not use conftest.py's ``client`` fixture, which drops and recreates the
schema. It never creates, migrates, or drops a database or schema.
"""

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, delete, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db_models import ItemDB, StockMovementDB
from app.services.stock import InsufficientStockError, register_stock_movement


DATABASE_NAME = "inventory_stock_concurrency_test"
DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1"}
DATABASE_PORT = 15432
SYNC_TIMEOUT_SECONDS = 8
LOCK_TIMEOUT = "12s"


def _dedicated_database_url():
    database_url = os.getenv("STOCK_CONCURRENCY_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail(
            "STOCK_CONCURRENCY_TEST_DATABASE_URL es obligatorio para esta "
            "prueba; configura una base PostgreSQL dedicada ya migrada."
        )

    try:
        url = make_url(database_url)
    except Exception:
        pytest.fail("STOCK_CONCURRENCY_TEST_DATABASE_URL no es una URL válida.")

    # Validate the target before create_engine() can open a connection. Never
    # include the URL or its credentials in assertion/error output.
    if not url.drivername.startswith("postgresql"):
        pytest.fail("La base de concurrencia debe usar PostgreSQL.")
    if url.host not in DATABASE_HOSTS:
        pytest.fail("El host debe ser localhost o una dirección loopback.")
    if url.port != DATABASE_PORT:
        pytest.fail(f"El puerto de pruebas debe ser {DATABASE_PORT}.")
    if url.database != DATABASE_NAME:
        pytest.fail(
            f"El nombre de base debe ser exactamente {DATABASE_NAME}; "
            "no se conectará a otra base."
        )
    return database_url


def test_concurrent_stock_outputs_serialize_on_postgresql():
    database_url = _dedicated_database_url()
    engine = create_engine(
        database_url,
        connect_args={
            "connect_timeout": 5,
            "options": f"-c lock_timeout={LOCK_TIMEOUT}",
        },
        pool_size=3,
        max_overflow=0,
        pool_timeout=SYNC_TIMEOUT_SECONDS,
    )

    item_id = None
    release_first = threading.Event()
    first_has_row_lock = threading.Event()
    second_is_waiting = threading.Event()
    second_backend_pid = None
    state_lock = threading.Lock()

    def hold_first_after_lock(connection, _cursor, statement, _params, _context, _many):
        if (
            threading.current_thread().name.startswith("stock-out_0")
            and "FOR UPDATE" in statement.upper()
        ):
            first_has_row_lock.set()
            if not release_first.wait(SYNC_TIMEOUT_SECONDS):
                raise TimeoutError(
                    "Timeout esperando liberar el bloqueo de la primera salida."
                )

    def observe_second_lock_attempt(
        connection, _cursor, statement, _params, _context, _many
    ):
        nonlocal second_backend_pid
        if (
            threading.current_thread().name.startswith("stock-out_1")
            and "FOR UPDATE" in statement.upper()
        ):
            # psycopg 3 exposes the backend PID on the raw driver connection.
            raw_connection = connection.connection.driver_connection
            with state_lock:
                second_backend_pid = raw_connection.info.backend_pid
            second_is_waiting.set()

    event.listen(engine, "after_cursor_execute", hold_first_after_lock)
    event.listen(engine, "before_cursor_execute", observe_second_lock_attempt)

    try:
        # This connection verifies the actual database identity before writes.
        with engine.connect() as connection:
            actual_database = connection.scalar(text("SELECT current_database()"))
            if actual_database != DATABASE_NAME:
                pytest.fail(
                    "La conexión llegó a una base distinta de la base dedicada; "
                    "no se insertaron datos."
                )

        unique_code = f"CONC-{uuid.uuid4().hex[:20]}"
        with engine.begin() as connection:
            item = ItemDB(
                code=unique_code,
                name="Concurrency test item",
                unit="pcs",
                quantity_available=5,
                minimum_stock=1,
                active=True,
            )
            connection.execute(
                ItemDB.__table__.insert().values(
                    code=item.code,
                    name=item.name,
                    unit=item.unit,
                    quantity_available=item.quantity_available,
                    minimum_stock=item.minimum_stock,
                    active=item.active,
                )
            )
            item_id = connection.scalar(
                select(ItemDB.id).where(ItemDB.code == unique_code)
            )
            assert item_id is not None

        def attempt_output():
            try:
                # Each worker owns an independent SQLAlchemy Session/connection.
                with Session(engine) as session:
                    movement = register_stock_movement(
                        session, item_id, "OUT", 4
                    )
                    return ("success", movement.id)
            except InsufficientStockError:
                return ("insufficient_stock", None)

        def first_output():
            return attempt_output()

        with ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="stock-out",
        ) as executor:
            first_future = executor.submit(first_output)
            if not first_has_row_lock.wait(SYNC_TIMEOUT_SECONDS):
                release_first.set()
                pytest.fail(
                    "La primera salida no adquirió SELECT FOR UPDATE dentro "
                    "del timeout."
                )

            second_future = executor.submit(attempt_output)
            if not second_is_waiting.wait(SYNC_TIMEOUT_SECONDS):
                release_first.set()
                pytest.fail(
                    "La segunda salida no llegó a SELECT FOR UPDATE dentro "
                    "del timeout."
                )

            deadline = time.monotonic() + SYNC_TIMEOUT_SECONDS
            observed_lock_wait = False
            while time.monotonic() < deadline:
                with engine.connect() as monitor:
                    wait_type = monitor.scalar(
                        text(
                            "SELECT wait_event_type FROM pg_stat_activity "
                            "WHERE pid = :pid"
                        ),
                        {"pid": second_backend_pid},
                    )
                if wait_type == "Lock":
                    observed_lock_wait = True
                    break
                time.sleep(0.05)

            if not observed_lock_wait:
                release_first.set()
                pytest.fail(
                    "PostgreSQL no mostró a la segunda sesión esperando un lock; "
                    "no se puede confirmar que la contención fuese real."
                )

            release_first.set()
            try:
                results = [
                    first_future.result(timeout=SYNC_TIMEOUT_SECONDS),
                    second_future.result(timeout=SYNC_TIMEOUT_SECONDS),
                ]
            except TimeoutError:
                pytest.fail(
                    "Las salidas concurrentes no terminaron dentro del timeout."
                )

        assert sorted(result[0] for result in results) == [
            "insufficient_stock",
            "success",
        ], f"Resultados inesperados de las salidas: {results!r}"

        with Session(engine) as verification_session:
            item = verification_session.get(ItemDB, item_id)
            assert item is not None
            assert item.quantity_available == 1
            confirmed_outputs = verification_session.scalars(
                select(StockMovementDB).where(
                    StockMovementDB.item_id == item_id,
                    StockMovementDB.movement_type == "OUT",
                )
            ).all()
            assert len(confirmed_outputs) == 1
            assert confirmed_outputs[0].quantity == 4
    finally:
        # Release a thread even when an assertion or synchronization step fails.
        release_first.set()
        event.remove(engine, "after_cursor_execute", hold_first_after_lock)
        event.remove(engine, "before_cursor_execute", observe_second_lock_attempt)

        try:
            if item_id is not None:
                # Delete only this test's rows, movement first to satisfy FK.
                with engine.begin() as connection:
                    connection.execute(
                        delete(StockMovementDB).where(
                            StockMovementDB.item_id == item_id
                        )
                    )
                    connection.execute(
                        delete(ItemDB).where(ItemDB.id == item_id)
                    )
        finally:
            engine.dispose()
