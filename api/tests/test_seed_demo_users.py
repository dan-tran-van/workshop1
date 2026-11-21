import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import BackendTestCase
from app.models import User
from app.services.auth import verify_password
from seed_demo_users import seed_demo_users


class TestDemoUserSeeding(BackendTestCase):
    def test_creates_distinct_role_accounts_and_assigns_owner(self) -> None:
        restaurant = self.restaurant()

        credentials = seed_demo_users(self.db)
        self.db.commit()

        self.assertEqual({role for role, _, _ in credentials}, {"ADMIN", "OWNER", "ANALYST"})
        self.assertEqual(len({password for _, _, password in credentials}), 3)
        for role, email, password in credentials:
            user = self.db.query(User).filter(User.email == email).one()
            self.assertEqual(user.role, role)
            self.assertGreaterEqual(len(password), 12)
            self.assertTrue(verify_password(password, user.password_hash))
            self.assertNotEqual(password, user.password_hash)
            if role == "OWNER":
                self.assertEqual([item.id for item in user.restaurants], [restaurant["id"]])
            else:
                self.assertEqual(user.restaurants, [])

    def test_refuses_to_seed_without_restaurants_or_over_existing_demo_users(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Seed at least one restaurant"):
            seed_demo_users(self.db)

        self.restaurant()
        seed_demo_users(self.db)
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "Demo users already exist"):
            seed_demo_users(self.db)


if __name__ == "__main__":
    unittest.main()
