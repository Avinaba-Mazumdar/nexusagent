#!/usr/bin/env python3
"""
NexusAgent scheduled cleanup: expired guest sessions and old audit rows.
Purges guest users older than specified TTL (default 24 hours).
Foreign keys automatically cascade deletion to:
  - rate_limit_buckets
  - documents (guest-uploaded)
  - document_chunks

Usage:
  python scripts/prune_guests.py
  python scripts/prune_guests.py --ttl 12
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add apps/backend to sys.path so backend imports resolve
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps" / "backend"))

from app.db.neon import neon_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("prune_guests")


async def main():
    parser = argparse.ArgumentParser(description="Prune expired guest sessions from Neon PostgreSQL.")
    parser.add_argument(
        "--ttl",
        type=int,
        default=24,
        help="TTL in hours. Guests older than this will be permanently purged (default: 24).",
    )
    parser.add_argument(
        "--audit-days",
        type=int,
        default=30,
        help="Retention for tool_audit_logs in days (default: 30).",
    )
    args = parser.parse_args()

    logger.info("Initializing Neon PostgreSQL connection pool...")
    connected = await neon_db.connect()
    if not connected:
        logger.error("Failed to connect to Neon database. Please check NEON_DATABASE_URL.")
        sys.exit(1)

    try:
        logger.info(f"Running guest TTL pruner for records older than {args.ttl} hours...")
        deleted_count = await neon_db.prune_expired_guests(ttl_hours=args.ttl)
        logger.info(f"Cleanup complete. Total pruned guest sessions: {deleted_count}")

        audit_deleted = await neon_db.prune_audit_logs(retention_days=args.audit_days)
        logger.info(f"Total audit rows older than {args.audit_days} days removed: {audit_deleted}")
    finally:
        await neon_db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
