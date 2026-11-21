import hmac
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Restaurant, User
from app.schemas import (
    AuthSetupResponse,
    BootstrapRequest,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.auth import TOKEN_TTL_SECONDS, create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(tags=["Authentication"])
bearer_scheme = HTTPBearer(auto_error=False)
ROLES = {"OWNER", "ANALYST", "ADMIN"}


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A valid email address is required")
    return normalized


def _normalize_name(full_name: str) -> str:
    normalized = full_name.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A full name is required")
    return normalized


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        restaurant_ids=sorted(restaurant.id for restaurant in user.restaurants),
    )


def _issue_token(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=TOKEN_TTL_SECONDS,
        user=_user_response(user),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = int(claims["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or user.role != claims.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or access has changed", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: str):
    def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action")
        return user
    return role_dependency


def ensure_restaurant_access(restaurant: Restaurant, user: User) -> None:
    if user.role == "OWNER" and all(owned.id != restaurant.id for owned in user.restaurants):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")


def _assign_restaurants(db: Session, restaurant_ids: List[int]) -> List[Restaurant]:
    unique_ids = set(restaurant_ids)
    restaurants = db.query(Restaurant).filter(Restaurant.id.in_(unique_ids)).all() if unique_ids else []
    if len(restaurants) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more restaurant IDs do not exist")
    return restaurants


@router.get("/auth/setup", response_model=AuthSetupResponse)
def auth_setup(db: Session = Depends(get_db)) -> AuthSetupResponse:
    return AuthSetupResponse(setup_required=db.query(User.id).first() is None)


@router.post("/auth/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User.id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator setup has already been completed")
    if not settings.AUTH_BOOTSTRAP_KEY or not hmac.compare_digest(payload.setup_key, settings.AUTH_BOOTSTRAP_KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator setup is not enabled or the setup key is invalid")
    email = _normalize_email(payload.email)
    if len(payload.password) < 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 12 characters")
    user = User(email=email, full_name=_normalize_name(payload.full_name), password_hash=hash_password(payload.password), role="ADMIN")
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    return _issue_token(user)


@router.get("/auth/me", response_model=UserResponse)
def current_user_profile(user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)


@router.get("/admin/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("ADMIN")),
) -> List[UserResponse]:
    return [_user_response(user) for user in db.query(User).order_by(User.id.asc()).all()]


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("ADMIN")),
) -> UserResponse:
    email = _normalize_email(payload.email)
    if len(payload.password) < 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 12 characters")
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
    if payload.role != "OWNER" and payload.restaurant_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Restaurant assignments are only valid for owners")
    user = User(
        email=email,
        full_name=_normalize_name(payload.full_name),
        password_hash=hash_password(payload.password),
        role=payload.role,
        restaurants=_assign_restaurants(db, payload.restaurant_ids),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("ADMIN")),
) -> UserResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("role", user.role) != "OWNER" and changes.get("restaurant_ids"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Restaurant assignments are only valid for owners")
    if user.id == admin.id and (changes.get("role", user.role) != "ADMIN" or changes.get("is_active", user.is_active) is False):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot remove your own administrator access")
    if user.role == "ADMIN" and (changes.get("role", user.role) != "ADMIN" or changes.get("is_active", user.is_active) is False):
        active_admins = db.query(User).filter(User.role == "ADMIN", User.is_active.is_(True)).count()
        if active_admins <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one active administrator must remain")
    if "role" in changes:
        user.role = changes["role"]
        if user.role != "OWNER":
            user.restaurants = []
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    if "restaurant_ids" in changes:
        user.restaurants = _assign_restaurants(db, changes["restaurant_ids"])
    db.commit()
    db.refresh(user)
    return _user_response(user)
