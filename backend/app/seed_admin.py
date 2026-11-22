"""Create a user interactively.

Run:
  docker compose exec api python -m app.seed_admin                  (admin)
  docker compose exec api python -m app.seed_admin --role guard
  docker compose exec api python -m app.seed_admin --role registrar
"""
import argparse
import getpass

from sqlalchemy import select

from .auth import hash_password
from .db import SessionLocal
from .models import User

ROLES = ("admin", "registrar", "guard")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=ROLES, default="admin")
    args = parser.parse_args()

    email = input(f"{args.role} email: ").strip().lower()
    name = input("Full name: ").strip()
    password = getpass.getpass("Password (min 12 chars): ")
    if len(password) < 12:
        raise SystemExit("Password too short.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("User already exists.")
        db.add(User(name=name, email=email, role=args.role, password_hash=hash_password(password)))
        db.commit()
    print(f"{args.role} created.")


if __name__ == "__main__":
    main()
