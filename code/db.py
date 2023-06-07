import itertools
import logging
from argparse import ArgumentParser, Namespace

import data
import psycopg2
from psycopg2.extras import NamedTupleCursor


class AddressDB:
    """Connect to the GNAF Postgres database and query for addresses. See https://github.com/minus34/gnaf-loader"""

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
            try:
                logging.info("Creating DB index...")
                self.cur.execute("CREATE index address_name_state on address_principals (locality_name, state)")
                conn.commit()
            except psycopg2.errors.DuplicateTable:
                logging.info("Skipping index creation as already exists")
                conn.rollback()

    def get_addresses(self, target_suburb: str, target_state: str) -> data.AddressList:
        """Return a list of Address for the provided suburb+state from the database."""
        query = """
            SELECT gnaf_pid, address, postcode, latitude, longitude
            FROM address_principals
            WHERE locality_name = %s AND state = %s
            LIMIT 100000"""

        self.cur.execute(query, (target_suburb, target_state))

        addresses = [
            data.Address(
                name=f"{row.address} {target_suburb} {row.postcode}",
                gnaf_pid=row.gnaf_pid,
                location=(float(row.longitude), float(row.latitude)),
            )
            for row in self.cur.fetchall()
        ]

        return addresses

    def get_list_vs_total(self, suburbs_states: dict) -> dict:
        """Calculate which fraction of the entire dataset is represented by the given list of state+suburb."""
        self.cur.execute("SELECT state, COUNT(*) FROM address_principals GROUP BY state")
        states = {row.state: {"total": row.count} for row in self.cur.fetchall()}

        query_parts = ["(state = %s AND locality_name IN %s)\n"] * len(suburbs_states)
        values = [[state, tuple(suburbs)] for state, suburbs in suburbs_states.items()]
        all_values = tuple(itertools.chain.from_iterable(values))

        query = f"""
            SELECT state, COUNT(*)
            FROM address_principals
            WHERE\n{" OR ".join(query_parts)}
            GROUP BY state
        """
        self.cur.execute(query, all_values)  # takes ~2 minutes
        for row in self.cur.fetchall():
            states[row.state]["completed"] = row.count

        # add a totals row
        total_completed = sum(sp.get("completed", 0) for sp in states.values())
        total = sum(sp.get("total", 0) for sp in states.values())
        states["total"] = {"completed": total_completed, "total": total}

        return states

    def get_counts_by_suburb(self) -> dict:
        """return a tally of addresses by state and suburb"""
        query = f"""
            SELECT locality_name, state, COUNT(*)
            FROM address_principals
            GROUP BY locality_name, state
            ORDER BY state, locality_name
        """
        self.cur.execute(query)

        results = {}
        for record in self.cur.fetchall():
            if record.state not in results:
                results[record.state] = {}
            results[record.state][record.locality_name] = record.count

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
    parser.add_argument("-H", "--dbhost", help="The hostname for the database", default="localhost")
    parser.add_argument("-P", "--dbport", help="The port number for the database", default="5433")
    parser.add_argument(
        "-i",
        "--create_index",
        help="Whether to disable adding an index to the DB to help speed up queries (only used for GitHub Actions)",
        action="store_false",
    )


def connect_to_db(args: Namespace) -> AddressDB:
    """return a DB connection based on the provided args"""
    return AddressDB(
        "postgres",
        args.dbhost,
        args.dbport,
        args.dbuser,
        args.dbpassword,
        args.create_index,
    )
