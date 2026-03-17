"""Seed the first super admin user.

Usage:
    python -m app.scripts.seed_admin <email>
"""
import asyncio
import sys
import os

# Ensure backend dir is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(env_path)
env_path2 = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path2)

from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User


async def seed_admin(email: str):
    email = email.lower().strip()
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            if existing.role == "super_admin":
                print(f"User {email} is already a super_admin.")
            else:
                existing.role = "super_admin"
                existing.is_active = True
                await db.commit()
                print(f"Updated {email} to super_admin.")
        else:
            user = User(email=email, role="super_admin", is_active=True)
            db.add(user)
            await db.commit()
            print(f"Created super_admin: {email}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.seed_admin <email>")
        sys.exit(1)

    email = sys.argv[1]
    asyncio.run(seed_admin(email))


if __name__ == "__main__":
    main()
