from types import SimpleNamespace
from unittest import mock

from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.management import call_command

from apps.runs.management.commands import artifact_bucket


def test_create_is_retried_while_the_store_starts():
    client = mock.Mock()
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadBucket"
    )
    client.create_bucket.side_effect = [
        EndpointConnectionError(endpoint_url="http://s3:8333"),
        None,
    ]
    storage = SimpleNamespace(
        bucket=object(),
        bucket_name="artifacts",
        connection=SimpleNamespace(meta=SimpleNamespace(client=client)),
    )

    with (
        mock.patch.object(artifact_bucket, "storages", {"artifacts": storage}),
        mock.patch.object(artifact_bucket.time, "sleep"),
    ):
        call_command("artifact_bucket")

    assert client.create_bucket.call_count == 2
