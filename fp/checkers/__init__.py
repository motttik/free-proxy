"""
Proxy Checkers Module

Модули для проверки работоспособности прокси
"""

from fp.checkers.sync_checker import SyncProxyChecker
from fp.checkers.async_checker import AsyncProxyChecker

__all__ = [
    "SyncProxyChecker",
    "AsyncProxyChecker",
]
