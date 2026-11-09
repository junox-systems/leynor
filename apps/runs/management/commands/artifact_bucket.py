"""Check the artifacts bucket on every start; create it only where asked.

Production buckets are provisioned outside the app (its credentials need no
create permission), so production startup only checks. Dev and CI smoke pass
--create against their SeaweedFS.
"""

import time

from botocore.exceptions import BotoCoreError, ClientError
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError


class StoreNotReady(Exception):
    """The object store answered, but with a server error: try again."""


class Command(BaseCommand):
    help = "Check the S3 bucket reel artifacts live in, waiting for the object store to come up."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wait", type=int, default=60, help="Seconds to wait for the object store."
        )
        parser.add_argument(
            "--create",
            action="store_true",
            help="Create the bucket if it is missing (dev, CI).",
        )

    def handle(self, *args, wait, create, **options):
        storage = storages["artifacts"]
        if not hasattr(storage, "bucket"):
            self.stdout.write("Artifacts storage is not S3; nothing to check.")
            return
        client, name = storage.connection.meta.client, storage.bucket_name
        deadline = time.monotonic() + wait
        while True:
            try:
                self._ensure(client, name, create)
                return
            except (BotoCoreError, StoreNotReady) as exc:  # still starting, or a blip
                if time.monotonic() > deadline:
                    raise CommandError(
                        f"Object store unreachable after {wait}s: {exc}"
                    ) from exc
                time.sleep(2)

    def _ensure(self, client, name, create):
        try:
            client.head_bucket(Bucket=name)
            self.stdout.write(f"Artifacts bucket {name} is ready.")
            return
        except ClientError as exc:
            status = exc.response["ResponseMetadata"].get("HTTPStatusCode", 0)
            if status >= 500:
                raise StoreNotReady(exc) from exc
            if status != 404:  # 403: wrong keys or no permission on the bucket
                raise CommandError(f"Artifacts bucket {name}: {exc}") from exc
            if not create:
                raise CommandError(
                    f"Artifacts bucket {name} does not exist. Create it with your "
                    "S3 provider, or set APP_ARTIFACT_BUCKET."
                ) from exc
        try:
            client.create_bucket(Bucket=name)
        except ClientError as race:  # another container created it first
            if race.response["Error"]["Code"] not in (
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            ):
                raise
        self.stdout.write(f"Created artifacts bucket {name}.")
