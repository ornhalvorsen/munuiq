"""
CLI entry point: python -m app.analytics --mode full|discover|incremental|backfill-groups
"""

import argparse
import sys

from app.analytics.connection import connect, close
from app.analytics.refresh import refresh


def main():
    parser = argparse.ArgumentParser(
        description="MUNUIQ Analytics — pre-computed analytics layer"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "discover", "incremental", "backfill-groups"],
        default="full",
        help="Refresh mode (default: full)",
    )
    parser.add_argument(
        "--date-from",
        help="Start date for incremental mode (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date-to",
        help="End date for incremental mode (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    # Connect
    conn = connect()
    if conn is None and args.mode != "discover":
        print("ERROR: Could not connect to database")
        sys.exit(1)

    try:
        result = refresh(
            mode=args.mode,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        if result and isinstance(result, dict) and result.get("failed"):
            sys.exit(1)
    finally:
        close()


if __name__ == "__main__":
    main()
