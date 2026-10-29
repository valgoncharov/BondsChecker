import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    """Логирует необработанную ошибку и помечает апдейт обработанным."""
    logger.error(
        "Необработанная ошибка в апдейте %s",
        event.update.update_id,
        exc_info=event.exception,
    )
    return True


def register_error_handlers(dp: Dispatcher) -> None:
    dp.errors.register(on_error)
