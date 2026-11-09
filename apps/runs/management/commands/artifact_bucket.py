"""Create the artifacts bucket if it is missing. Safe to run on every start."""

import time

from botocore.exceptions import BotoCoreError, ClientError
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the S3 bucket reel artifacts live in, waiting for the object store to come up."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wait", type=int, default=60, help="Seconds to wait for the object store."
        )

    def handle(self, *args, wait, **options):
        storage = storages["artifacts"]
        if not hasattr(storage, "bucket"):
            self.stdout.write("Artifacts storage is not S3; nothing to create.")
            return
        client, name = storage.connection.meta.client, storage.bucket_name
        deadline = time.monotonic() + wait
        while True:
            try:
                self._ensure(client, name)
                return
            except BotoCoreError as exc:  # store still starting: connection refused
                if time.monotonic() > deadline:
                    raise CommandError(
                        f"Object store unreachable after {wait}s: {exc}"
                    ) from exc
                time.sleep(2)

    def _ensure(self, client, name):
        try:
            client.head_bucket(Bucket=name)
            self.stdout.write(f"Artifacts bucket {name} is ready.")
            return
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise CommandError(f"Artifacts bucket {name}: {exc}") from exc
        try:
            client.create_bucket(Bucket=name)
        except ClientError as race:  # another container created it first
            if race.response["Error"]["Code"] not in (
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            ):
                raise
        self.stdout.write(f"Created artifacts bucket {name}.")
