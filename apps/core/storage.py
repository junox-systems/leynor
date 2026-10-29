# apps/core/storage.py

from functools import cached_property

from storages.backends.s3 import S3Storage


class PublicEndpointS3Storage(S3Storage):
    """S3 storage that talks to an internal endpoint but hands out public URLs.

    In docker-stack the app reaches the object store as http://s3:9000, a
    hostname browsers can't resolve. Uploads keep using AWS_S3_ENDPOINT_URL;
    url() signs against `public_endpoint_url` instead. Presigned URLs embed the
    host in the signature, so the public host must be used at signing time —
    rewriting the URL afterwards would invalidate it.
    """

    def __init__(self, *, public_endpoint_url=None, **settings):
        self.public_endpoint_url = public_endpoint_url
        super().__init__(**settings)

    @cached_property
    def _public(self):
        # A separate instance rather than swapping self.endpoint_url during
        # url(): this storage is shared across threads.
        return S3Storage(endpoint_url=self.public_endpoint_url)

    def url(self, name, *args, **kwargs):
        if not self.public_endpoint_url:
            return super().url(name, *args, **kwargs)
        return self._public.url(name, *args, **kwargs)
