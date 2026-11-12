"""
CLI utility for one-time or server-operator bootstrap of an AUREVON AI owner account.

Usage:
  python -m backend.scripts.bootstrap_owner --username owner --email owner@example.com --password "..."
  or set OWNER_USERNAME / OWNER_EMAIL / OWNER_PASSWORD in environment and pass --from-env
"""
import argparse
import asyncio
import getpass
import sys

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.database.session import AsyncSessionLocal, init_db
from backend.app.repositories.user_repo import UserRepository


async def run_bootstrap(
    username: str,
    email: str,
    password: str,
    promote_existing: bool = False,
) -> int:
    await init_db()
    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        owner_exists = await repo.has_any_owner()

        existing_by_email = await repo.get_by_email(email)
        existing_by_username = await repo.get_by_username(username)

        if promote_existing and existing_by_email:
            updated = await repo.set_role(existing_by_email.id, "owner")
            print(f"Promoted existing user '{updated.username}' ({updated.email}) to role='owner'.")
            return 0

        if owner_exists:
            print("Error: An owner account already exists. Pass --promote-existing with an existing email to add a co-owner.")
            return 1

        if existing_by_email or existing_by_username:
            print("Error: Username or email already exists. Pass --promote-existing to elevate an existing account.")
            return 1

        if len(password) < 8:
            print("Error: Owner password must be at least 8 characters long.")
            return 1

        user = await repo.create(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="owner",
            is_active=True,
        )
        print(f"Created AUREVON AI platform owner '{user.username}' ({user.email}) [id={user.id}].")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap AUREVON AI platform owner account.")
    parser.add_argument("--username", help="Owner username")
    parser.add_argument("--email", help="Owner email")
    parser.add_argument("--password", help="Owner password (prompted if omitted)")
    parser.add_argument("--from-env", action="store_true", help="Read OWNER_USERNAME, OWNER_EMAIL, OWNER_PASSWORD from environment")
    parser.add_argument("--promote-existing", action="store_true", help="Promote an existing user by email to owner")
    args = parser.parse_args()

    username = args.username or (settings.OWNER_USERNAME if args.from_env else None)
    email = args.email or (settings.OWNER_EMAIL if args.from_env else None)
    password = args.password or (settings.OWNER_PASSWORD if args.from_env else None)

    if not email:
        email = input("Owner email: ").strip()
    if not username and not args.promote_existing:
        username = input("Owner username: ").strip()
    if not password and not args.promote_existing:
        password = getpass.getpass("Owner password (min 8 chars): ")

    username = username or email.split("@")[0]
    password = password or ""

    return asyncio.run(
        run_bootstrap(
            username=username,
            email=email,
            password=password,
            promote_existing=args.promote_existing,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
