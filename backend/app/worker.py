"""Worker process for background jobs (auto-deprecation, etc.)."""

import asyncio
import logging

from app.jobs.auto_deprecate import deprecation_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting background worker...")
    await deprecation_loop(interval_seconds=300)


if __name__ == "__main__":
    asyncio.run(main())
