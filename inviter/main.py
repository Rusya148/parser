import asyncio
import logging
import os

from telethon import TelegramClient

from config.settings import load_settings
from db.session import create_engine, create_sessionmaker, init_db
from service import InviterService


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger("telegram-inviter")


async def main() -> None:
    logger = setup_logging()
    settings = load_settings()

    os.makedirs("sessions", exist_ok=True)
    session_path = os.path.join("sessions", settings.session_name)

    engine = create_engine(settings.database_url)
    await init_db(engine)
    sessionmaker = create_sessionmaker(engine)

    async with TelegramClient(session_path, settings.api_id, settings.api_hash) as client:
        inviter = InviterService(
            client=client,
            sessionmaker=sessionmaker,
            target_chat=settings.invite_target_chat,
            invites_per_hour=settings.invites_per_hour,
            window_start=settings.invite_window_start,
            window_end=settings.invite_window_end,
            timezone=settings.invite_timezone,
            logger=logger,
        )
        await inviter.run()


if __name__ == "__main__":
    asyncio.run(main())
