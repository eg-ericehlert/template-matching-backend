#!/usr/bin/env python3
import os
import sys
import logging
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Load connection info from environment
    db_host = os.getenv("RDS_HOST")
    db_port = os.getenv("RDS_PORT", "5432")
    db_name = os.getenv("RDS_DBNAME")
    db_user = os.getenv("RDS_USER")
    db_pass = os.getenv("RDS_PASSWORD")

    # Log what we've got (masking the password)
    logging.debug(f"RDS_HOST     = {db_host!r}")
    logging.debug(f"RDS_PORT     = {db_port!r}")
    logging.debug(f"RDS_DBNAME   = {db_name!r}")
    logging.debug(f"RDS_USER     = {db_user!r}")
    logging.debug(f"RDS_PASSWORD set? {bool(db_pass)}")

    # Check for missing variables
    missing = [name for name, val in [
        ("RDS_HOST", db_host),
        ("RDS_DBNAME", db_name),
        ("RDS_USER", db_user),
        ("RDS_PASSWORD", db_pass)
    ] if not val]
    if missing:
        logging.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Attempt to connect
    try:
        logging.info("Connecting to the database…")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_pass
        )
        logging.info("Connection established.")
    except Exception as e:
        logging.exception("Failed to connect to the database")
        sys.exit(1)

    # Do the insert
    try:
        with conn:
            with conn.cursor() as cur:
                logging.info("Inserting into testing.test…")
                cur.execute(
                    "INSERT INTO testing (test) VALUES (%s);",
                    (1,)
                )
                logging.info("Insert successful.")
    except Exception as e:
        logging.exception("Failed during insert")
    finally:
        conn.close()
        logging.info("Database connection closed.")

if __name__ == "__main__":
    main()