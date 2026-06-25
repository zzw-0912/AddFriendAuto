from sqlalchemy.orm import Session

from app.models.contact import Contact


def search_contacts(q: str, db: Session) -> list[Contact]:
    query = db.query(Contact).filter(Contact.status == "active")
    if q:
        like = f"%{q}%"
        query = query.filter(
            Contact.wechat_nickname.ilike(like) | Contact.wechat_id.ilike(like)
        )
    return query.limit(50).all()
