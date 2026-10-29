from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.orgs.models import Organization
from apps.users.models import User, user_avatar_path


def image_upload(name="avatar.png", size=None, dimensions=(10, 10)):
    buffer = BytesIO()
    Image.new("RGB", dimensions, "red").save(buffer, "PNG")
    data = buffer.getvalue()
    if size:
        data = data + b"\0" * (size - len(data))
    return SimpleUploadedFile(name, data, content_type="image/png")


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", username="alice", password="s3cret-pw"
        )
        self.client.force_login(self.user)

    def test_profile_post_updates_name_and_username(self):
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Alice",
                "last_name": "Liddell",
                "username": "alice-l",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alice")
        self.assertEqual(self.user.last_name, "Liddell")
        self.assertEqual(self.user.username, "alice-l")

    def test_profile_post_stores_avatar(self):
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "",
                "last_name": "",
                "username": "alice",
                "avatar": image_upload(),
            },
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

    def test_profile_post_without_avatar_keeps_existing_avatar(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        avatar_name = self.user.avatar.name

        self.client.post(
            reverse("profile"),
            {
                "first_name": "Alice",
                "last_name": "",
                "username": "alice",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar.name, avatar_name)

    def test_profile_renders_avatar_image(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, 'class="avatar')
        self.assertContains(response, "<img")

    def test_profile_rejects_non_image_avatar(self):
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "",
                "last_name": "",
                "username": "alice",
                "avatar": SimpleUploadedFile("not-an-image.txt", b"nope"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("avatar", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_profile_rejects_oversized_avatar(self):
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "",
                "last_name": "",
                "username": "alice",
                "avatar": image_upload("big.png", size=6 * 1024 * 1024),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("avatar", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_profile_rejects_huge_pixel_avatar(self):
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "",
                "last_name": "",
                "username": "alice",
                "avatar": image_upload("huge.png", dimensions=(4097, 4097)),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("avatar", response.context["form"].errors)

    def test_profile_saves_when_stored_avatar_file_is_missing(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        self.user.avatar.storage.delete(self.user.avatar.name)

        response = self.client.post(
            reverse("profile"),
            {"first_name": "Alice", "last_name": "", "username": "alice"},
        )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alice")

    def test_invalid_post_does_not_show_unsaved_values(self):
        User.objects.create_user(
            email="bob@example.com", username="bob", password="s3cret-pw"
        )
        response = self.client.post(
            reverse("profile"),
            {"first_name": "Mallory", "last_name": "", "username": "bob"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertNotContains(response, "@bob")
        self.assertEqual(response.context["user"].first_name, "")

    def test_username_taken_ignores_case(self):
        User.objects.create_user(
            email="bob@example.com", username="bob", password="s3cret-pw"
        )
        response = self.client.post(
            reverse("profile"),
            {"first_name": "", "last_name": "", "username": "BOB"},
        )
        self.assertIn(
            "A user with that username already exists.",
            response.context["form"].non_field_errors(),
        )

    def test_db_rejects_case_insensitive_duplicate_username(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email="other@example.com", username="ALICE", password="s3cret-pw"
            )

    def test_username_case_change_of_own_name_allowed(self):
        response = self.client.post(
            reverse("profile"),
            {"first_name": "", "last_name": "", "username": "Alice"},
        )
        self.assertRedirects(response, reverse("profile"))

    def test_profile_renders_edit_form(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_profile_can_clear_avatar(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        storage = User._meta.get_field("avatar").storage
        avatar_name = self.user.avatar.name

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("profile"),
                {
                    "first_name": "",
                    "last_name": "",
                    "username": "alice",
                    "avatar-clear": "on",
                },
            )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        self.assertFalse(storage.exists(avatar_name))


class AvatarWidgetTests(TestCase):
    """The avatar field renders a preview + upload/remove, not Django's default text."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="finn@example.com", username="finn", password="s3cret-pw"
        )
        self.client.force_login(self.user)

    def test_without_avatar_offers_upload_only(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, 'data-controller="avatar-preview"')
        self.assertContains(response, "Upload photo")
        self.assertNotContains(response, "Currently:")
        self.assertNotContains(response, 'name="avatar-clear"')

    def test_with_avatar_offers_change_and_remove(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Change photo")
        self.assertContains(response, 'name="avatar-clear"')

    def test_remove_clears_avatar(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        response = self.client.post(
            reverse("profile"), {"username": "finn", "avatar-clear": "on"}
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_rejected_upload_still_previews_current_avatar(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        response = self.client.post(
            reverse("profile"),
            {"username": "finn", "avatar": SimpleUploadedFile("x.txt", b"nope")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change photo")
        self.assertContains(response, 'name="avatar-clear"')


class AvatarFilesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="erin@example.com", username="erin", password="s3cret-pw"
        )

    def test_replacing_avatar_deletes_old_file(self):
        self.user.avatar.save("one.png", image_upload("one.png"), save=True)
        old_name = self.user.avatar.name
        storage = User._meta.get_field("avatar").storage
        self.assertTrue(storage.exists(old_name))

        with self.captureOnCommitCallbacks(execute=True):
            self.user.avatar.save("two.png", image_upload("two.png"), save=True)

        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(self.user.avatar.name))

    def test_avatar_path_unique_per_upload(self):
        # Storage-independent: S3 overwrites same-named keys instead of renaming.
        first = user_avatar_path(self.user, "image.JPG")
        second = user_avatar_path(self.user, "image.JPG")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith(f"users/user_{self.user.id}/"))
        self.assertTrue(first.endswith(".jpg"))

    def test_deleting_user_deletes_avatar_and_thumbnail(self):
        self.user.avatar.save("avatar.png", image_upload(), save=True)
        thumbnail = self.user.avatar_thumbnail
        thumbnail.generate()
        thumb_name = thumbnail.name
        storage = User._meta.get_field("avatar").storage
        self.assertTrue(storage.exists(self.user.avatar.name))
        self.assertTrue(storage.exists(thumb_name))

        self.client.force_login(self.user)
        self.client.post(reverse("account_reauthenticate"), {"password": "s3cret-pw"})
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("delete_account"), {"confirm": self.user.email})

        self.assertFalse(storage.exists(self.user.avatar.name))
        self.assertFalse(storage.exists(thumb_name))

    def test_delete_rolls_back_org_changes_when_user_delete_fails(self):
        Organization.create_with_owner("Solo", self.user)
        self.client.force_login(self.user)
        self.client.post(reverse("account_reauthenticate"), {"password": "s3cret-pw"})

        with mock.patch.object(User, "delete", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("delete_account"), {"confirm": self.user.email}
                )

        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Organization.objects.filter(name="Solo").exists())
