import sqlglot

from fakesnow.transforms import database_as_schema


def test_database_as_schema() -> None:
    assert (
        sqlglot.parse_one("SELECT * FROM marts.jaffles.customers").transform(database_as_schema).sql()
        == "SELECT * FROM marts_jaffles.customers"
    )

    assert (
        sqlglot.parse_one("SELECT * FROM jaffles.customers").transform(database_as_schema).sql()
        == "SELECT * FROM jaffles.customers"
    )

    assert (
        sqlglot.parse_one("SELECT * FROM customers").transform(database_as_schema).sql()
        == "SELECT * FROM customers"
    )

    assert (
        sqlglot.parse_one("CREATE SCHEMA marts.jaffles").transform(database_as_schema).sql()
        == "CREATE SCHEMA marts_jaffles"
    )

    assert (
        sqlglot.parse_one("create schema marts.jaffles").transform(database_as_schema).sql()
        == "CREATE SCHEMA marts_jaffles"
    )

    assert (
        sqlglot.parse_one("CREATE SCHEMA jaffles").transform(database_as_schema).sql()
        == "CREATE SCHEMA jaffles"
    )

    assert (
        sqlglot.parse_one("DROP SCHEMA marts.jaffles").transform(database_as_schema).sql()
        == "DROP SCHEMA marts_jaffles"
    )