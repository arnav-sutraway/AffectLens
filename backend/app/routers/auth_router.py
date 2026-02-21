"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserCreate, UserLogin, Token, UserResponse
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _role_str(role):
    """Get role as string (handles SQLite returning plain string instead of enum)."""
    return role.value if hasattr(role, "value") else str(role)


@router.post("/register", response_model=Token)
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        if db.query(User).filter(User.email == data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        role_val = (data.role or "viewer").lower()
        role = UserRole.director if role_val == "director" else UserRole.viewer
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(data={"sub": str(user.id)})
        return Token(access_token=token, user_id=user.id, role=_role_str(user.role))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=token, user_id=user.id, role=_role_str(user.role))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
