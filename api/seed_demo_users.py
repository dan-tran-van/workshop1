import secrets

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Restaurant, User
from app.services.auth import hash_password

DEMO_USERS = (
    ("Demo Administrator", "demo.admin@example.test", "ADMIN"),
    ("Demo Restaurant Owner", "demo.owner@example.test", "OWNER"),
    ("Demo F&B Analyst", "demo.analyst@example.test", "ANALYST"),
)


def seed_demo_users(db: Session) -> list[tuple[str, str, str]]:
    restaurant = db.query(Restaurant).order_by(Restaurant.id.asc()).first()
    if restaurant is None:
        raise RuntimeError("Seed at least one restaurant before creating demo users.")

    demo_emails = [email for _, email, _ in DEMO_USERS]
    existing = db.query(User.email).filter(User.email.in_(demo_emails)).all()
    if existing:
        emails = ", ".join(email for (email,) in existing)
        raise RuntimeError(
            f"Demo users already exist ({emails}); passwords are only shown when first generated."
        )

    credentials: list[tuple[str, str, str]] = []
    users: list[User] = []
    for full_name, email, role in DEMO_USERS:
        password = secrets.token_urlsafe(24)
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        if role == "OWNER":
            user.restaurants = [restaurant]
        users.append(user)
        credentials.append((role, email, password))

    db.add_all(users)
    return credentials


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as db:
        restaurant = db.query(Restaurant).order_by(Restaurant.id.asc()).first()
        if restaurant is None:
            raise RuntimeError("Seed at least one restaurant before creating demo users.")
        restaurant_name = restaurant.name
        restaurant_id = restaurant.id
        credentials = seed_demo_users(db)

    print("Demo accounts created. Save each password now; they cannot be recovered:")
    print(f"OWNER restaurant assignment: {restaurant_name} (ID {restaurant_id})")
    for role, email, password in credentials:
        print(f"{role}: {email} / {password}")


if __name__ == "__main__":
    main()
