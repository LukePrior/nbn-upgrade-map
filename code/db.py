import logging
import sqlite3
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace

import data
import psycopg2
from psycopg2.extras import NamedTupleCursor

SQLITE_FILE_EXTENSIONS = {"db", "sqlite", "sqlite3", "db3", "s3db", "sl3"}


class DbDriver(ABC):
    """Abstract class for DB connections."""

    @abstractmethod
    def execute(self, query, args=None):
        """Return a list of Namespace objects for the provided query."""
        pass


class AddressDB:
    """Connect to our cut-down version of the GNAF Postgres database and query for addresses."""

    def __init__(self, db: DbDriver):
        self.db = db

    def get_addresses(self, target_suburb: str, target_state: str) -> data.AddressList:
        """Return a list of Address for the provided suburb+state from the database."""
        query = """
            SELECT gnaf_pid, address, postcode, latitude, longitude
            FROM address_principals
            WHERE locality_name = %s AND state = %s
            LIMIT 100000"""

        return [
            data.Address(
                name=f"{row.address} {target_suburb} {row.postcode}",
                gnaf_pid=row.gnaf_pid,
                longitude=float(row.longitude),
                latitude=float(row.latitude),
            )
            for row in self.db.execute(query, (target_suburb, target_state))
        ]

    def get_counts_by_suburb(self) -> dict[str, dict[str, int]]:
        """return a tally of addresses by state and suburb"""
        query = """
            SELECT locality_name, state, COUNT(*) as count
            FROM address_principals
            GROUP BY locality_name, state
            ORDER BY state, locality_name
        """

        results = {}
        for record in self.db.execute(query):
            if record.state not in results:
                results[record.state] = {}
            results[record.state][record.locality_name] = record.count

        return results

    def get_extents_by_suburb(self) -> dict:
        """return the bounding box for each state/suburb as a tuple of (min_lat, min_long), (max_lat, max_long)"""
        query = """
            SELECT locality_name, state,
                min(latitude) as min_lat,
                max(latitude) as max_lat,
                min(longitude) as min_long,
                max(longitude) as max_long
            FROM address_principals
            GROUP BY locality_name, state
            ORDER BY state, locality_name
        """

        results = {}
        for record in self.db.execute(query):
            if record.state not in results:
                results[record.state] = {}
            results[record.state][record.locality_name] = (
                (float(record.min_lat), float(record.min_long)),
                (float(record.max_lat), float(record.max_long)),
            )

        return results


def add_db_arguments(parser: ArgumentParser):
    """Add arguments to the provided parser for connecting to the DB"""
    parser.add_argument("-u", "--dbuser", help="The name of the database user", default="postgres")
    parser.add_argument(
        "-p",
        "--dbpassword",
        help="The password for the database user",
        default="password",
    )
    parser.add_argument(
        "-H", "--dbhost", help="The hostname for the database (or file-path for Sqlite)", default="localhost"
    )
    parser.add_argument("-P", "--dbport", help="The port number for the database", default="5433")
    parser.add_argument(
        "-i",
        "--create_index",
        help="Whether to disable adding an index to the DB to help speed up queries (only used for GitHub Actions)",
        action="store_false",
    )


class PostgresDb(DbDriver):
    """Class that implements Postgresql DB connection."""

    def __init__(self, database: str, host: str, port: str, user: str, password: str, create_index: bool = True):
        """Connect to the database"""
        conn = psycopg2.connect(
            database=database, host=host, port=port, user=user, password=password, cursor_factory=NamedTupleCursor
        )

        self.cur = conn.cursor()

        # detect the schema used by the DB
        self.cur.execute("SELECT schema_name FROM information_schema.schemata where schema_name like 'gnaf_%'")
        db_schema = self.cur.fetchone().schema_name
        self.cur.execute(f"SET search_path TO {db_schema}")
        conn.commit()

        # optionally create a DB index
        if create_index:
            logging.info("Creating DB index...")
            self.cur.execute(
                "CREATE INDEX IF NOT EXISTS address_name_state ON address_principals (locality_name, state)"
            )
            conn.commit()

    def execute(self, query, args=None):
        """Return a list of Namespace objects for the provided query."""
        self.cur.execute(query, args)
        return self.cur.fetchall()


class SqliteDb(DbDriver):
    """Class that implements Sqlite DB connection (to a file). Pass the filename as the dbhost."""

    def __init__(self, database_file: str):
        """Connect to the database"""
        conn = sqlite3.connect(database_file)
        conn.row_factory = sqlite3.Row
        self.cur = conn.cursor()

    def execute(self, query, args=None):
        """Return a list of Namespace objects for the provided query."""
        query = query.replace("%s", "?")
        if args is None:
            args = {}
        logging.info("Executing query: %s", query)
        self.cur.execute(query, args)
        # sqlite doesn't support NamedTupleCursor, so we need to manually add the column names
        return [Namespace(**dict(zip(x.keys(), x))) for x in self.cur.fetchall()]


def connect_to_db(args: Namespace) -> AddressDB:
    """return a DB connection based on the provided args"""
    if args.dbhost.split(".")[-1] in SQLITE_FILE_EXTENSIONS:
        db = SqliteDb(args.dbhost)
    else:
        db = PostgresDb(
            "postgres",
            args.dbhost,
            args.dbport,
            args.dbuser,
            args.dbpassword,
            args.create_index,
        )
    return AddressDB(db)
