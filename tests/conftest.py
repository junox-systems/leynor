import os

import pytest

os.environ.setdefault(
    "REEL_DB", "postgresql://postgres:postgres@127.0.0.1:5432/reel_test"
)


@pytest.fixture(scope="session", autouse=True)
def schema():
    from reel_playbook.db import migrate

    migrate()


@pytest.fixture(autouse=True)
def clean():
    from reel_playbook.db import setup
    from reel_playbook.db import models as m

    setup()
    for model in (
        m.Artifact,
        m.Blob,
        m.CacheKey,
        m.Cue,
        m.Gate,
        m.Log,
        m.Render,
        m.Project,
    ):
        model.objects.all().delete()
    yield
