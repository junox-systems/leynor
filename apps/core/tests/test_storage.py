from django.test import SimpleTestCase, override_settings

from apps.core.storage import PublicEndpointS3Storage

S3_SETTINGS = {
    "AWS_ACCESS_KEY_ID": "test-key",
    "AWS_SECRET_ACCESS_KEY": "test-secret",
    "AWS_STORAGE_BUCKET_NAME": "media",
    "AWS_S3_ENDPOINT_URL": "http://s3:9000",
    "AWS_S3_CUSTOM_DOMAIN": None,
    "AWS_S3_REGION_NAME": "us-east-1",
}


# Signing is local (no network), so fake credentials are enough.
@override_settings(**S3_SETTINGS)
class PublicEndpointS3StorageTests(SimpleTestCase):
    def test_url_signed_against_public_endpoint(self):
        storage = PublicEndpointS3Storage(public_endpoint_url="https://cdn.example.com")
        url = storage.url("avatars/a.png")
        self.assertTrue(url.startswith("https://cdn.example.com/media/"), url)
        self.assertIn("Signature", url)
        # Uploads still go through the internal endpoint.
        self.assertEqual(storage.endpoint_url, "http://s3:9000")

    def test_falls_back_to_internal_endpoint(self):
        url = PublicEndpointS3Storage().url("avatars/a.png")
        self.assertTrue(url.startswith("http://s3:9000/media/"), url)
