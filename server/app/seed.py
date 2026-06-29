import random
import string

from sqlalchemy import text

from app.core.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.feedback import Feedback
from app.models.plan import Plan
from app.models.user import User


def init_db():
    Base.metadata.create_all(bind=engine)

    # Add columns to existing tables if missing (SQLite compat)
    if "sqlite" in str(engine.url):
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
                conn.commit()
        except Exception:
            pass
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE memberships ADD COLUMN plan_id INTEGER"))
                conn.commit()
        except Exception:
            pass

    if "sqlite" in str(engine.url):
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN referral_code VARCHAR(16)"))
                conn.commit()
        except Exception:
            pass

    db = SessionLocal()
    try:
        users_missing = db.query(User).filter(User.referral_code.is_(None)).all()
        existing_codes = {u.referral_code for u in db.query(User.referral_code).filter(User.referral_code.isnot(None)).all()}
        chars = string.ascii_uppercase + string.digits
        for u in users_missing:
            for _ in range(100):
                code = "".join(random.choices(chars, k=6))
                if code not in existing_codes:
                    u.referral_code = code
                    existing_codes.add(code)
                    break
        if users_missing:
            db.commit()

        if not db.query(Plan).first():
            plans = [
                Plan(name="月卡", duration_days=30, price_cents=2999, enabled=True),
                Plan(name="季卡", duration_days=90, price_cents=6999, enabled=True),
                Plan(name="年卡", duration_days=365, price_cents=19999, enabled=True),
            ]
            db.add_all(plans)
            db.commit()

        if not db.query(AdminUser).first():
            admin = AdminUser(
                username="admin",
                password_hash=hash_password("admin123"),
                role="super_admin",
                status="active",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
