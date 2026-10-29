# apps/api/schemas/user.py

import uuid

import msgspec


class UserSchema(msgspec.Struct):
    """User response schema."""

    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str


class UserPathParams(msgspec.Struct):
    """Path parameters for user detail endpoint."""

    user_id: uuid.UUID
