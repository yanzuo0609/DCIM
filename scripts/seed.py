"""Run database seed manually."""

import asyncio

from app.core.database import async_session_factory, init_db
from app.core.seed import seed_defaults


async def main() -> None:
    await init_db()
    async with async_session_factory() as session:
        await seed_defaults(session)
    print("Seed completed.")


if __name__ == "__main__":
    asyncio.run(main())
