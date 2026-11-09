from types import SimpleNamespace
from unittest import mock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.management import CommandError, call_command

from apps.runs.management.commands import artifact_bucket


def error(status):
    return ClientError(
        {
            "Error": {"Code": str(status)},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "HeadBucket",
    )


def run(client, *args):
    storage = SimpleNamespace(
        bucket=object(),
        bucket_name="artifacts",
        connection=SimpleNamespace(meta=SimpleNamespace(client=client)),
    )
    with (
        mock.patch.object(artifact_bucket, "storages", {"artifacts": storage}),
        mock.patch.object(artifact_bucket.time, "sleep"),
    ):
        call_command("artifact_bucket", *args)


def test_create_is_retried_while_the_store_starts():
    client = mock.Mock()
    client.head_bucket.side_effect = error(404)
    client.create_bucket.side_effect = [
        EndpointConnectionError(endpoint_url="http://s3:8333"),
        None,
    ]
    run(client, "--create")
    assert client.create_bucket.call_count == 2


def test_a_server_error_is_retried():
    client = mock.Mock()
    client.head_bucket.side_effect = [error(503), None]
    run(client)
    assert client.head_bucket.call_count == 2


def test_without_create_a_missing_bucket_fails_and_nothing_is_created():
    client = mock.Mock()
    client.head_bucket.side_effect = error(404)
    with pytest.raises(CommandError, match="does not exist"):
        run(client)
    client.create_bucket.assert_not_called()


def test_forbidden_fails_at_once():
    client = mock.Mock()
    client.head_bucket.side_effect = error(403)
    with pytest.raises(CommandError, match="artifacts"):
        run(client, "--create")
    assert client.head_bucket.call_count == 1
