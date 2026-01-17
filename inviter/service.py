from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    UserAlreadyParticipantError,
    UserNotMutualContactError,
    UserPrivacyRestrictedError,
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import Channel, User

from db.models import ActiveUser, InvitedUser


class InviterService:
    def __init__(
        self,
        client: TelegramClient,
        sessionmaker,
        target_chat: str,
        invites_per_hour: int,
        window_start: int,
        window_end: int,
        timezone,
        invite_immediate_on_start: bool,
        logger: logging.Logger,
    ) -> None:
        self.client = client
        self.sessionmaker = sessionmaker
        self.target_chat = target_chat
        self.invites_per_hour = invites_per_hour
        self.window_start = window_start
        self.window_end = window_end
        self.timezone = timezone
        self.invite_immediate_on_start = invite_immediate_on_start
        self.logger = logger

    async def run(self) -> None:
        chat = await self.client.get_entity(self.target_chat)
        if not isinstance(chat, Channel):
            raise RuntimeError("INVITE_TARGET_CHAT must be a channel or megagroup")
        self.logger.info("Inviter target channel resolved: %s", self.target_chat)

        if self.invite_immediate_on_start:
            await self._invite_first_candidate(chat)

        while True:
            now = datetime.now(self.timezone)
            if not self._is_within_window(now):
                sleep_seconds = self._seconds_until_window(now)
                self.logger.info(
                    "Outside invite window. Sleeping for %s seconds", sleep_seconds
                )
                await asyncio.sleep(sleep_seconds)
                continue

            sleep_seconds = await self._invite_for_current_hour(chat, now)
            await asyncio.sleep(sleep_seconds)

    def _is_within_window(self, current: datetime) -> bool:
        return self.window_start <= current.hour < self.window_end

    def _seconds_until_window(self, current: datetime) -> int:
        if current.hour < self.window_start:
            start = current.replace(
                hour=self.window_start, minute=0, second=0, microsecond=0
            )
        else:
            next_day = current + timedelta(days=1)
            start = next_day.replace(
                hour=self.window_start, minute=0, second=0, microsecond=0
            )
        return max(1, int((start - current).total_seconds()))

    async def _invite_for_current_hour(self, chat, now: datetime) -> int:
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        slot_seconds = int(3600 / max(1, self.invites_per_hour))

        async with self.sessionmaker() as session:
            already_invited = await session.scalar(
                select(func.count(InvitedUser.id)).where(
                    InvitedUser.invited_at >= hour_start,
                    InvitedUser.invited_at < hour_end,
                )
            )
            remaining = self.invites_per_hour - int(already_invited or 0)
            if remaining <= 0:
                next_hour = hour_end
                wait_seconds = max(1, int((next_hour - now).total_seconds()))
                self.logger.info("Hourly limit reached. Waiting %s seconds.", wait_seconds)
                return wait_seconds

            next_slot_time = hour_start + timedelta(
                seconds=slot_seconds * int(already_invited or 0)
            )
            if now < next_slot_time:
                wait_seconds = max(1, int((next_slot_time - now).total_seconds()))
                self.logger.info(
                    "Waiting for next slot in %s seconds.", wait_seconds
                )
                return wait_seconds

            candidates = await session.execute(
                select(ActiveUser)
                .outerjoin(
                    InvitedUser, InvitedUser.username == ActiveUser.username
                )
                .where(InvitedUser.username.is_(None))
                .order_by(ActiveUser.created_at.asc())
                .limit(1)
            )
            users = list(candidates.scalars().all())

        if not users:
            self.logger.info("No candidates to invite.")
            return 60

        for user in users:
            await self._invite_single(chat, user)
            break

        next_slot_time = hour_start + timedelta(
            seconds=slot_seconds * (int(already_invited or 0) + 1)
        )
        wait_seconds = max(1, int((next_slot_time - datetime.now(self.timezone)).total_seconds()))
        return wait_seconds

    async def _invite_first_candidate(self, chat) -> None:
        async with self.sessionmaker() as session:
            candidates = await session.execute(
                select(ActiveUser)
                .outerjoin(
                    InvitedUser, InvitedUser.username == ActiveUser.username
                )
                .where(InvitedUser.username.is_(None))
                .order_by(ActiveUser.created_at.asc())
                .limit(1)
            )
            user = candidates.scalars().first()

        if not user:
            self.logger.info("No candidates to invite on start.")
            return

        self.logger.info("Inviting first candidate on start: %s", user.username)
        await self._invite_single(chat, user)
    async def _invite_single(self, chat, user: ActiveUser) -> None:
        username = user.username.lstrip("@")
        status = "invited"
        error = None

        try:
            entity = await self.client.get_entity(username)
            if not isinstance(entity, User):
                raise RuntimeError("Unsupported user entity type")
            await self.client(InviteToChannelRequest(chat, [entity]))
            self.logger.info("Invited %s (@%s)", user.first_name, username)
        except UserAlreadyParticipantError:
            status = "already"
        except UserPrivacyRestrictedError:
            status = "privacy"
        except UserNotMutualContactError:
            status = "not_mutual"
        except PeerFloodError as exc:
            status = "peer_flood"
            error = str(exc)
            self.logger.warning("Peer flood limit hit. Sleeping for 1 hour.")
            await asyncio.sleep(3600)
        except FloodWaitError as exc:
            status = "flood_wait"
            error = str(exc)
            wait_time = exc.seconds + 1
            self.logger.warning("Flood wait for %s seconds", wait_time)
            await asyncio.sleep(wait_time)
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = str(exc)
            self.logger.exception("Failed to invite %s", username)

        await self._store_invited_user(user, status, error)

    async def _store_invited_user(
        self, user: ActiveUser, status: str, error: str | None
    ) -> None:
        async with self.sessionmaker() as session:
            session.add(
                InvitedUser(
                    username=user.username,
                    first_name=user.first_name,
                    status=status,
                    error=error,
                )
            )
            await session.commit()
