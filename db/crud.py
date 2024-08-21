from sqlalchemy.orm import Session
from db import models

def create_user(db: Session, user_id: int, email: str):
    db_user = models.User(id=user_id, email=email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def delete_user(db: Session, user_id: int, email: str):
    user = db.query(models.User).filter(models.User.id == user_id, models.User.email == email).first()
    if user:
        db.delete(user)
        db.commit()
        return True
    return False
