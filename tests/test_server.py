# ruff: noqa: E501

import threading
from collections.abc import Iterator
from decimal import Decimal
from time import sleep
from typing import Callable

import pytest
import snowflake.connector
import uvicorn
from snowflake.connector.cursor import ResultMetadata

import fakesnow.server


@pytest.fixture(scope="session")
def unused_port(unused_tcp_port_factory: Callable[[], int]) -> int:
    # unused_tcp_port_factory is from pytest-asyncio
    return unused_tcp_port_factory()


@pytest.fixture(scope="session")
def server(unused_tcp_port_factory: Callable[[], int]) -> Iterator[dict]:
    port = unused_tcp_port_factory()
    server = uvicorn.Server(uvicorn.Config(fakesnow.server.app, port=port, log_level="info"))
    thread = threading.Thread(target=server.run, name="Server", daemon=True)
    thread.start()

    while not server.started:
        sleep(0.1)

    yield dict(
        user="fake",
        password="snow",
        account="fakesnow",
        host="localhost",
        port=port,
        protocol="http",
        # disable telemetry
        session_parameters={"CLIENT_OUT_OF_BAND_TELEMETRY_ENABLED": False},
    )

    server.should_exit = True
    # wait for server thread to end
    thread.join()


@pytest.fixture
def sconn(server: dict) -> Iterator[snowflake.connector.SnowflakeConnection]:
    with snowflake.connector.connect(
        **server,
        database="db1",
        schema="schema1",
        # disable infinite retries on error
        network_timeout=1,
    ) as c:
        yield c


@pytest.fixture
def scur(
    sconn: snowflake.connector.SnowflakeConnection,
) -> Iterator[snowflake.connector.cursor.SnowflakeCursor]:
    with sconn.cursor() as cur:
        yield cur


def test_server_types_no_result_set(sconn: snowflake.connector.SnowflakeConnection) -> None:
    cur = sconn.cursor()
    cur.execute(
        """
        create or replace table example (
            XBOOLEAN BOOLEAN, XINT INT, XFLOAT FLOAT, XDECIMAL DECIMAL(10,2),
            XVARCHAR VARCHAR
        )
        """
    )
    cur.execute("select * from example")
    # fmt: off
    assert cur.description == [
        ResultMetadata(name='XBOOLEAN', type_code=13, display_size=None, internal_size=None, precision=None, scale=None, is_nullable=True),
        # TODO: is_nullable should be False
        ResultMetadata(name='XINT', type_code=0, display_size=None, internal_size=None, precision=38, scale=0, is_nullable=True),
        ResultMetadata(name='XFLOAT', type_code=1, display_size=None, internal_size=None, precision=None, scale=None, is_nullable=True),
        ResultMetadata(name="XDECIMAL", type_code=0, display_size=None, internal_size=None, precision=10, scale=2, is_nullable=True),
        # TODO: internal_size matches column size
        ResultMetadata(name="XVARCHAR", type_code=2, display_size=None, internal_size=16777216, precision=None, scale=None, is_nullable=True)
    ]
    # fmt: on


def test_server_types(scur: snowflake.connector.cursor.SnowflakeCursor) -> None:
    scur.execute(
        # TODO: match columns names without using AS
        """
        select true as TRUE, 1::int as "1::INT", 2.0::float as "2.0::FLOAT", to_decimal('12.3456', 10,2) as "TO_DECIMAL('12.3456', 10,2)",
        'hello' as "'HELLO'"
        """
    )
    assert scur.fetchall() == [(True, 1, 2.0, Decimal("12.35"), "hello")]


def test_server_abort_request(server: dict) -> None:
    with (
        snowflake.connector.connect(
            **server,
            # triggers an abort request
            network_timeout=0,
        ) as conn1,
        conn1.cursor() as cur,
    ):
        cur.execute("select 'will abort'")


def test_server_errors(scur: snowflake.connector.cursor.SnowflakeCursor) -> None:
    cur = scur
    with pytest.raises(snowflake.connector.errors.ProgrammingError) as excinfo:
        cur.execute("select * from this_table_does_not_exist")

    assert excinfo.value.errno == 2003
    assert excinfo.value.sqlstate == "42S02"
    assert excinfo.value.msg
    assert "THIS_TABLE_DOES_NOT_EXIST" in excinfo.value.msg
