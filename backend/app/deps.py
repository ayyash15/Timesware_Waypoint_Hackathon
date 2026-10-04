from datetime import datetime, timedelta
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from .config import SECRET_KEY
from .db import get_db
from . import models as m


def make_token(user: m.User) -> str:
    return jwt.encode({"sub": str(user.id), "exp": datetime.utcnow() + timedelta(hours=24)}, SECRET_KEY, algorithm="HS256")


def current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> m.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not signed in")
    try:
        data = jwt.decode(authorization[7:], SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, please sign in again")
    user = db.get(m.User, int(data["sub"]))
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def require(*roles):
    def dep(user: m.User = Depends(current_user)) -> m.User:
        if user.role not in roles:
            raise HTTPException(403, f"This area is for: {", ".join(roles)}")
        return user
    return dep
