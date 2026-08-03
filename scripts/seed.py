"""Run database seed manually.

Usage (from repository root):

    backend\\.venv\\Scripts\\python.exe scripts\\seed.py

Or:

    cd backend
    .\\.venv\\Scripts\\python.exe -c "import runpy; runpy.run_path(r'..\\scripts\\seed.py', run_name='__main__')"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import async_session_factory, init_db  # noqa: E402
from app.core.seed import seed_defaults  # noqa: E402


async def main() -> None:
    await init_db()
    async with async_session_factory() as session:
        await seed_defaults(session)
    print("Seed completed.")


if __name__ == "__main__":
    asyncio.run(main())
