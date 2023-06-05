import logging

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
