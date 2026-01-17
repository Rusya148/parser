from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import User

from db.models import ActiveUser


class TelegramParser:
    def __init__(
        self,
        client: TelegramClient,
        sessionmaker,
        target_chat_names: list[str],
        analysis_days: int,
        min_messages: int,
        logger: logging.Logger,
    ) -> None:
        self.client = client
        self.sessionmaker = sessionmaker
        self.target_chat_names = target_chat_names
        self.analysis_days = analysis_days
        self.min_messages = min_messages
        self.logger = logger

    async def run(self) -> None:
        chats = await self._find_target_chats()
        if not chats:
            self.logger.warning("No target chats found. Nothing to parse.")
            return

        for chat in chats:
            await self._analyze_chat(chat)

    async def _find_target_chats(self) -> list:
        targets = [name.lower() for name in self.target_chat_names]
        found: dict[str, object] = {}
        async for dialog in self._iter_dialogs_with_floodwait():
            title = (dialog.title or "").strip()
            title_key = title.lower()
            for target in targets:
                if target in title_key:
                    if target not in found:
                        found[target] = dialog.entity
                    break

        missing = [name for name in self.target_chat_names if name.lower() not in found]
        if missing:
            self.logger.warning("Chats not found: %s", ", ".join(missing))
        self.logger.info("Found %s chats", len(found))
        return list(found.values())

    async def _analyze_chat(self, chat) -> None:
        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=self.analysis_days)
        counts: dict[int, int] = defaultdict(int)
        users: dict[int, User] = {}
        saved_user_ids: set[int] = set()

        self.logger.info("Analyzing chat: %s", getattr(chat, "title", str(chat)))
        async with self.sessionmaker() as session:
            async for message in self._iter_messages_with_floodwait(chat, date_to):
                if message.date < date_from:
                    break
                if message.action is not None:
                    continue
                sender = await message.get_sender()
                if not isinstance(sender, User):
                    continue
                if sender.bot or sender.deleted:
                    continue
                if not sender.username:
                    continue

                counts[sender.id] += 1
                users[sender.id] = sender

                if counts[sender.id] > self.min_messages and sender.id not in saved_user_ids:
                    saved_user_ids.add(sender.id)
                    username = f"@{sender.username}"
                    session.add(
                        ActiveUser(
                            username=username,
                            first_name=sender.first_name,
                        )
                    )
                    await session.commit()
                    self.logger.info(
                        "Saved active user %s (%s) in chat '%s'",
                        sender.first_name,
                        username,
                        getattr(chat, "title", ""),
                    )

        self.logger.info(
            "Active users saved in chat '%s': %s",
            getattr(chat, "title", ""),
            len(saved_user_ids),
        )

    async def _iter_dialogs_with_floodwait(self):
        while True:
            try:
                async for dialog in self.client.iter_dialogs():
                    yield dialog
                break
            except FloodWaitError as exc:
                wait_time = exc.seconds + 1
                self.logger.warning("Flood wait for %s seconds while dialogs", wait_time)
                await asyncio.sleep(wait_time)

    async def _iter_messages_with_floodwait(self, chat, date_to):
        offset_id = 0
        while True:
            try:
                async for message in self.client.iter_messages(
                    chat, offset_date=date_to, offset_id=offset_id
                ):
                    yield message
                    offset_id = message.id
                break
            except FloodWaitError as exc:
                wait_time = exc.seconds + 1
                self.logger.warning("Flood wait for %s seconds while messages", wait_time)
                await asyncio.sleep(wait_time)
