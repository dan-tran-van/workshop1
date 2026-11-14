import os
import sys
from datetime import datetime, timedelta, timezone

# Add api directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models import Restaurant, Review, SyncTarget
from app.services.analysis import get_or_run_restaurant_analysis


def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if data already exists
    if db.query(Restaurant).count() > 0:
        print("Database already contains restaurant data. Skipping seed.")
        db.close()
        return

    print("Seeding initial restaurants and reviews...")

    now = datetime.now(timezone.utc)

    # 1. Golden Lotus Bistro
    r1 = Restaurant(
        google_place_id="ChIJ_golden_lotus_001",
        name="Golden Lotus Bistro",
        address="142 Le Loi Street, District 1, Ho Chi Minh City",
        google_rating=4.4,
        user_rating_count=320,
        last_synced_at=now
    )
    db.add(r1)
    db.flush()

    r1_reviews = [
        Review(
            restaurant_id=r1.id,
            external_review_id="rev_gl_1",
            author_name="Linh Tran",
            rating=5.0,
            text="The caramelized pork belly and lotus salad were extraordinary! The dining area has a lovely cozy ambience and peaceful lighting. Perfect for dates.",
            published_at=now - timedelta(days=2)
        ),
        Review(
            restaurant_id=r1.id,
            external_review_id="rev_gl_2",
            author_name="David Miller",
            rating=3.0,
            text="Food is flavorful, but we waited nearly 40 minutes for our main dishes on a Saturday night. The staff seemed overwhelmed and forgot our drink refills.",
            published_at=now - timedelta(days=5)
        ),
        Review(
            restaurant_id=r1.id,
            external_review_id="rev_gl_3",
            author_name="Minh Hoang",
            rating=5.0,
            text="Staff is very polite and the presentation of dishes is top notch. Spotless cutlery and immaculate hygiene standards. A bit pricey but worth it.",
            published_at=now - timedelta(days=8)
        ),
        Review(
            restaurant_id=r1.id,
            external_review_id="rev_gl_4",
            author_name="Sophie Becker",
            rating=2.0,
            text="Long queue outside despite having a booking. Service was slow and dishes arrived lukewarm. Expected much better for this price point.",
            published_at=now - timedelta(days=12)
        ),
        Review(
            restaurant_id=r1.id,
            external_review_id="rev_gl_5",
            author_name="Kenji Sato",
            rating=4.0,
            text="Great taste and authentic Vietnamese flavours with a modern twist. The mango coconut dessert is a must-try!",
            published_at=now - timedelta(days=16)
        ),
    ]
    db.add_all(r1_reviews)

    # 2. Sakura Ramen Bar
    r2 = Restaurant(
        google_place_id="ChIJ_sakura_ramen_002",
        name="Sakura Ramen Bar",
        address="88 Nguyen Thi Minh Khai, District 3, Ho Chi Minh City",
        google_rating=4.1,
        user_rating_count=185,
        last_synced_at=now
    )
    db.add(r2)
    db.flush()

    r2_reviews = [
        Review(
            restaurant_id=r2.id,
            external_review_id="rev_sr_1",
            author_name="An Nguyen",
            rating=4.0,
            text="Rich, creamy tonkotsu broth and perfectly springy chashu noodles. The open kitchen looks very clean and hygienic.",
            published_at=now - timedelta(days=3)
        ),
        Review(
            restaurant_id=r2.id,
            external_review_id="rev_sr_2",
            author_name="Brian Wilson",
            rating=2.0,
            text="Broth was overwhelmingly salty today, couldn't finish half the bowl. The wooden stools are uncomfortable and tightly packed together.",
            published_at=now - timedelta(days=7)
        ),
        Review(
            restaurant_id=r2.id,
            external_review_id="rev_sr_3",
            author_name="Thao Pham",
            rating=5.0,
            text="Super fast service! Food arrived in less than 7 minutes after ordering via QR code. Highly recommended for quick business lunches.",
            published_at=now - timedelta(days=11)
        ),
    ]
    db.add_all(r2_reviews)

    # 3. Sync targets
    targets = [
        SyncTarget(
            target_type="place_id",
            value="ChIJ_golden_lotus_001",
            language_code="en",
            is_active=True,
            last_synced_at=now
        ),
        SyncTarget(
            target_type="place_id",
            value="ChIJ_sakura_ramen_002",
            language_code="en",
            is_active=True,
            last_synced_at=now
        ),
    ]
    db.add_all(targets)

    db.commit()
    print("Database seeded with sample restaurants, reviews, and sync targets.")

    # Generate initial cached analysis for Golden Lotus Bistro to demonstrate instant cached loads
    print("Generating initial cached analysis for Golden Lotus Bistro...")
    get_or_run_restaurant_analysis(db, r1.id)
    print("Seeding complete!")

    db.close()


if __name__ == "__main__":
    seed_data()
