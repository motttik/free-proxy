"""
Logging Utilities

Централизованная настройка логирования для free-proxy
"""

import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_logger(
    name: str,
    level: LogLevel = "WARNING",
    format_string: str | None = None,
) -> logging.Logger:
    """
    Настроить логгер для модуля

    Args:
        name: Имя логгера (обычно __name__)
        level: Уровень логирования
        format_string: Формат сообщений (по умолчанию стандартный)

    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)

    # Если уже настроен - возвращаем
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level))

    # Консольный обработчик
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level))

    # Формат
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Не распространять на корневой логгер
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер по имени

    Args:
        name: Имя логгера

    Returns:
        Логгер
    """
    return logging.getLogger(name)


class LogContext:
    """Контекстный менеджер для логирования с таймингом"""

    def __init__(self, logger: logging.Logger, message: str):
        self.logger = logger
        self.message = message

    def __enter__(self) -> "LogContext":
        self.logger.info(f"Starting: {self.message}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.logger.info(f"Completed: {self.message}")
        else:
            self.logger.error(f"Failed: {self.message} - {exc_val}")
