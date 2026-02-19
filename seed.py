"""
Run this once to create a test user in the database:
  python seed.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import create_tables, SessionLocal, User
from auth import hash_password

create_tables()
db = SessionLocal()

# ── Change these if you want ──────────────────────────────
EMAIL     = "test@vault-partners.eu"
PASSWORD  = "password123"
FULL_NAME = "Test User"
# ─────────────────────────────────────────────────────────

existing = db.query(User).filter(User.email == EMAIL).first()
if existing:
    print(f"User already exists: {EMAIL}")
else:
    user = User(
        email=EMAIL,
        hashed_password=hash_password(PASSWORD),
        full_name=FULL_NAME,
        is_admin=True
    )
    db.add(user)
    db.commit()
    print(f"✓ Test user created!")
    print(f"  Email:    {EMAIL}")
    print(f"  Password: {PASSWORD}")

db.close()
