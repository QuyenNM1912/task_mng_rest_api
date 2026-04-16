from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_refresh_token,
    verify_refresh_token,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_with_role,
)
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["Auth"])
admin = schemas.UserRole.admin


@router.post("/register", response_model=schemas.UserResponse, status_code=201)
@limiter.limit("1000/minute")
def register(request: Request, body: schemas.UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=body.email,
        password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
@limiter.limit("1000/minute")
def login(request: Request, body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token_str = create_refresh_token({"sub": str(user.id)})

    refresh_token = models.RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(refresh_token)
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token_str}


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    user = verify_refresh_token(body.refresh_token, db)
    
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token_str = create_refresh_token({"sub": str(user.id)})
    
    db.query(models.RefreshToken).filter(models.RefreshToken.token == body.refresh_token).delete()
    new_refresh_token = models.RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_refresh_token)
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token_str}


@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/admin/users/{user_id}/role", dependencies=[Depends(get_current_user_with_role(admin))])
def update_user_role(user_id: int, body: schemas.UserRoleUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role not in schemas.UserRole:
        raise HTTPException(status_code=400, detail="Invalid role")
    user.role = body.role
    db.commit()
    return {"message": "User role updated"}
