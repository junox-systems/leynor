# apps/users/tests/test_models.py
"""
Unit tests for user models.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTestCase(TestCase):
    """
    Test case for User model functionality.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_user_str(self):
        """User __str__ returns email."""
        self.assertEqual(str(self.user), "test@example.com")

    def test_email_is_normalized(self):
        """Email is lowercased and stripped on save."""
        user = User.objects.create_user(
            username="upper", email="  Upper@Example.COM  ", password="testpass123"
        )
        self.assertEqual(user.email, "upper@example.com")

    def test_username_is_stripped(self):
        """Username is stripped of whitespace on save."""
        user = User.objects.create_user(
            username="  spacey  ", email="spacey@example.com", password="testpass123"
        )
        self.assertEqual(user.username, "spacey")

    def test_email_is_username_field(self):
        """Email is the USERNAME_FIELD for authentication."""
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_uuid_primary_key(self):
        """User has UUID primary key from BaseModel."""
        import uuid

        self.assertIsInstance(self.user.id, uuid.UUID)
        # Time-ordered v7 keeps B-tree inserts append-only.
        self.assertEqual(self.user.id.version, 7)

    def test_timestamps_exist(self):
        """User has created_at and updated_at from BaseModel."""
        self.assertIsNotNone(self.user.created_at)
        self.assertIsNotNone(self.user.updated_at)

    def test_unique_email(self):
        """Duplicate email raises IntegrityError."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="other", email="test@example.com", password="testpass123"
            )

    def test_avatar_field_exists(self):
        """User model has avatar field."""
        self.assertTrue(hasattr(self.user, "avatar"))
        # Default is empty/None
        self.assertFalse(self.user.avatar)
