# apps/api/views.py

from http import HTTPStatus

import msgspec

from dmr import Controller
from dmr.components import Path
from dmr.errors import ErrorModel
from dmr.metadata import ResponseSpec
from dmr.plugins.msgspec import MsgspecSerializer
from dmr.response import APIError
from dmr.security.django_session import DjangoSessionSyncAuth

from apps.dashboard.panels import activity_payload
from apps.instagram.models import Reel, ReelPitch
from apps.instagram.panels import pitch_payload, route_payload
from apps.orgs.rbac import current_session
from apps.users.models import User

from .schemas.dashboard import ActivityEntrySchema
from .schemas.reel import PitchPathParams, ReelPathParams, RunStatusSchema
from .schemas.user import UserPathParams, UserSchema


class UserListController(Controller[MsgspecSerializer]):
    """List all users. Staff only — it exposes every user's email."""

    auth = [DjangoSessionSyncAuth()]
    responses = [ResponseSpec(ErrorModel, status_code=HTTPStatus.FORBIDDEN)]

    def get(self) -> list[UserSchema]:
        if not self.request.user.is_staff:
            raise APIError(
                self.format_error("Forbidden"),
                status_code=HTTPStatus.FORBIDDEN,
            )
        users = User.objects.all()
        return [
            UserSchema(
                id=u.id,
                username=u.username,
                email=u.email,
                first_name=u.first_name,
                last_name=u.last_name,
            )
            for u in users
        ]


class UserDetailController(Controller[MsgspecSerializer]):
    """Retrieve a single user by ID. Own record only, unless staff."""

    auth = [DjangoSessionSyncAuth()]
    responses = [ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND)]

    def get(self, parsed_path: Path[UserPathParams]) -> UserSchema:
        user_id = parsed_path.user_id
        try:
            # 404, not 403, for someone else's ID: don't confirm it exists.
            if user_id != self.request.user.id and not self.request.user.is_staff:
                raise User.DoesNotExist
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise APIError(
                self.format_error("User not found"),
                status_code=HTTPStatus.NOT_FOUND,
            )
        return UserSchema(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
        )


class DashboardActivityController(Controller[MsgspecSerializer]):
    """Refresh the dashboard activity feed for the current user."""

    auth = [DjangoSessionSyncAuth()]

    def get(self) -> list[ActivityEntrySchema]:
        payload = activity_payload(self.request.user)
        return [ActivityEntrySchema(**entry) for entry in payload["entries"]]


def _organization(controller):
    session = current_session(controller.request)
    return session.organization if session else None


class ReelRouteController(Controller[MsgspecSerializer]):
    """Poll a reel's route while its steps run. Another tenant's reel is a 404."""

    auth = [DjangoSessionSyncAuth()]
    responses = [ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND)]

    def get(self, parsed_path: Path[ReelPathParams]) -> RunStatusSchema:
        reel = (
            Reel.objects.prefetch_related("gates")
            .filter(
                pk=parsed_path.reel_id,
                campaign__project__organization=_organization(self),
            )
            .first()
        )
        if reel is None:
            raise APIError(
                self.format_error("Reel not found"), status_code=HTTPStatus.NOT_FOUND
            )
        return msgspec.convert(route_payload(reel), RunStatusSchema)


class ReelPitchController(Controller[MsgspecSerializer]):
    """Poll a pitch while its three concepts are written."""

    auth = [DjangoSessionSyncAuth()]
    responses = [ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND)]

    def get(self, parsed_path: Path[PitchPathParams]) -> RunStatusSchema:
        pitch = ReelPitch.objects.filter(
            pk=parsed_path.pitch_id,
            campaign__project__organization=_organization(self),
        ).first()
        if pitch is None:
            raise APIError(
                self.format_error("Pitch not found"), status_code=HTTPStatus.NOT_FOUND
            )
        return msgspec.convert(pitch_payload(pitch), RunStatusSchema)
