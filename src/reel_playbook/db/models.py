"""The schema. Plain tables, TEXT ids, no auto ids except Django's own bookkeeping."""

from django.db import models


class Project(models.Model):
    slug = models.TextField(primary_key=True)
    state = models.TextField()
    version = models.TextField()
    root = models.TextField()
    fps = models.IntegerField()
    width = models.IntegerField()
    height = models.IntegerField()
    duration_s = models.FloatField(null=True)
    max_attempts = models.IntegerField(default=3)
    tokens_json = models.TextField()
    locked_json = models.TextField()
    created_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        db_table = "projects"


class Blob(models.Model):
    sha256 = models.TextField(primary_key=True)
    ext = models.TextField()
    kind = models.TextField()
    media_type = models.TextField(null=True)
    bytes = models.BigIntegerField()
    data = models.BinaryField()
    created_at = models.TextField()

    class Meta:
        db_table = "blobs"


class Artifact(models.Model):
    slug = models.TextField()
    path = models.TextField()
    kind = models.TextField()
    text = models.TextField(null=True)
    sha256 = models.TextField(null=True)
    meta_json = models.TextField(null=True)
    created_at = models.TextField()

    class Meta:
        db_table = "artifacts"
        constraints = [
            models.UniqueConstraint(fields=["slug", "path"], name="artifact_pk"),
        ]


class Gate(models.Model):
    slug = models.TextField()
    step = models.TextField()
    result = models.TextField(null=True)
    attempts = models.IntegerField(default=0)
    evidence = models.TextField(null=True)
    at = models.TextField(null=True)

    class Meta:
        db_table = "gates"
        constraints = [
            models.UniqueConstraint(fields=["slug", "step"], name="gate_pk"),
        ]


class Log(models.Model):
    id = models.TextField(primary_key=True)
    slug = models.TextField()
    at = models.TextField()
    action = models.TextField()
    from_state = models.TextField()
    to_state = models.TextField()
    note = models.TextField(null=True)

    class Meta:
        db_table = "logs"


class Cue(models.Model):
    slug = models.TextField()
    idx = models.IntegerField()
    scene = models.IntegerField()
    start_s = models.FloatField()
    end_s = models.FloatField()
    text = models.TextField()

    class Meta:
        db_table = "cues"
        constraints = [
            models.UniqueConstraint(fields=["slug", "idx"], name="cue_pk"),
        ]


class Render(models.Model):
    id = models.TextField(primary_key=True)
    slug = models.TextField()
    sha256 = models.TextField()
    duration_s = models.FloatField(null=True)
    fps = models.FloatField(null=True)
    loudness = models.FloatField(null=True)
    peak = models.FloatField(null=True)
    verified_at = models.TextField(null=True)

    class Meta:
        db_table = "renders"


class CacheKey(models.Model):
    key = models.TextField(primary_key=True)
    sha256 = models.TextField()
    tool = models.TextField()
    tool_version = models.TextField()
    created_at = models.TextField()

    class Meta:
        db_table = "cache_keys"


class Idea(models.Model):
    slug = models.TextField(primary_key=True)
    sentence = models.TextField()
    insight = models.TextField()
    goal = models.TextField()
    score = models.FloatField()
    citations_json = models.TextField()
    alternatives_json = models.TextField()
    adversarial_json = models.TextField()
    created_at = models.TextField()

    class Meta:
        db_table = "ideas"


class Hook(models.Model):
    slug = models.TextField()
    idx = models.IntegerField()
    archetype = models.TextField()
    spoken = models.TextField()
    first_frame = models.TextField()
    overlay = models.TextField()
    chosen = models.BooleanField(default=False)
    objection = models.TextField(null=True)
    answer = models.TextField(null=True)

    class Meta:
        db_table = "hooks"
        constraints = [
            models.UniqueConstraint(fields=["slug", "idx"], name="hook_pk"),
        ]


class Beat(models.Model):
    slug = models.TextField()
    idx = models.IntegerField()
    name = models.TextField()
    purpose = models.TextField()
    overlay = models.TextField()
    visual_beat = models.TextField()
    seconds_est = models.FloatField()

    class Meta:
        db_table = "beats"
        constraints = [
            models.UniqueConstraint(fields=["slug", "idx"], name="beat_pk"),
        ]
