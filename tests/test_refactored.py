"""
Tests for refactored modules

Тесты для новых модулей: CLI utils, lazy imports, logging
"""

import pytest
import time
from unittest.mock import patch, MagicMock


class TestLazyImports:
    """Тесты lazy импортов"""

    def test_import_version(self):
        """Тест импорта версии"""
        import fp
        assert fp.__version__ == "3.0.0"
        assert fp.__author__ == "motttik"

    def test_lazy_import_freeproxy(self):
        """Тест lazy импорта FreeProxy"""
        import fp
        # Проверяем, что модуль еще не загружен
        assert "fp.core" not in __import__("sys").modules
        
        # Теперь импортируем
        from fp import FreeProxy
        assert FreeProxy is not None
        
        # Проверяем, что модуль загрузился
        assert "fp.core" in __import__("sys").modules

    def test_lazy_import_singletons(self):
        """Тест что lazy импорты возвращают тот же класс"""
        import fp
        from fp import FreeProxy as FP1
        from fp import FreeProxy as FP2
        assert FP1 is FP2

    def test_invalid_attribute(self):
        """Тест ошибки при импорте несуществующего атрибута"""
        import fp
        with pytest.raises(AttributeError):
            _ = fp.NonExistentAttribute


class TestCLIUtils:
    """Тесты CLI утилит"""

    def test_create_table(self):
        """Тест создания таблицы"""
        from fp.cli.utils import create_table
        table = create_table("Test", ["Col1", "Col2"])
        assert table.title == "Test"
        assert len(table.columns) == 2

    def test_format_proxy(self):
        """Тест форматирования прокси"""
        from fp.cli.utils import format_proxy
        assert "green" in format_proxy("http://1.2.3.4:8080")
        assert "cyan" in format_proxy("https://1.2.3.4:8080")
        assert "yellow" in format_proxy("socks4://1.2.3.4:1080")
        assert "magenta" in format_proxy("socks5://1.2.3.4:1080")

    def test_format_latency(self):
        """Тест форматирования задержки"""
        from fp.cli.utils import format_latency
        assert "green" in format_latency(50)
        assert "yellow" in format_latency(200)
        assert "red" in format_latency(600)

    def test_format_score(self):
        """Тест форматирования score"""
        from fp.cli.utils import format_score
        assert "green" in format_score(85)
        assert "yellow" in format_score(60)
        assert "red" in format_score(30)


class TestLogging:
    """Тесты логирования"""

    def test_setup_logger(self):
        """Тест настройки логгера"""
        from fp.utils.logging import setup_logger
        logger = setup_logger("test_logger", "DEBUG")
        assert logger.name == "test_logger"
        assert logger.level == 10  # DEBUG

    def test_get_logger(self):
        """Тест получения логгера"""
        from fp.utils.logging import get_logger
        logger = get_logger("existing_logger")
        assert logger.name == "existing_logger"

    def test_log_context_success(self, caplog):
        """Тест контекста логирования (успех)"""
        from fp.utils.logging import setup_logger, LogContext
        import logging
        
        logger = setup_logger("test_context", "INFO")
        
        with caplog.at_level(logging.INFO):
            with LogContext(logger, "test operation"):
                pass
        
        assert "Starting: test operation" in caplog.text
        assert "Completed: test operation" in caplog.text

    def test_log_context_failure(self, caplog):
        """Тест контекста логирования (ошибка)"""
        from fp.utils.logging import setup_logger, LogContext
        import logging
        
        logger = setup_logger("test_context_fail", "ERROR")
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                with LogContext(logger, "failing operation"):
                    raise ValueError("Test error")
        
        assert "Starting: failing operation" in caplog.text
        assert "Failed: failing operation" in caplog.text


class TestNewCLI:
    """Тесты нового CLI"""

    def test_cli_app_import(self):
        """Тест импорта CLI приложения"""
        from fp.cli.app import app
        assert app is not None

    def test_cli_get_command(self):
        """Тест команды get"""
        from fp.cli.commands.get import get_proxy
        assert get_proxy is not None

    @patch("fp.cli.commands.get.FreeProxy")
    def test_get_proxy_text(self, mock_freeproxy, capsys):
        """Тест получения прокси в текстовом формате"""
        from fp.cli.commands.get import get_proxy
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = "http://1.2.3.4:8080"
        mock_freeproxy.return_value = mock_instance
        
        get_proxy(
            country=None,
            timeout=5.0,
            randomize=False,
            count=1,
            format_output="text",
            https=False,
            protocol=None,
        )
        
        captured = capsys.readouterr()
        assert "Proxy" in captured.out

    @patch("fp.cli.commands.get.FreeProxy")
    def test_get_proxy_json(self, mock_freeproxy, capsys):
        """Тест получения прокси в JSON формате"""
        from fp.cli.commands.get import get_proxy
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = "http://1.2.3.4:8080"
        mock_freeproxy.return_value = mock_instance
        
        get_proxy(
            country=None,
            timeout=5.0,
            randomize=False,
            count=1,
            format_output="json",
            https=False,
            protocol=None,
        )
        
        captured = capsys.readouterr()
        assert "proxy" in captured.out
        assert "1.2.3.4:8080" in captured.out


class TestBackwardCompatibility:
    """Тесты обратной совместимости"""

    def test_old_import_style(self):
        """Тест старого стиля импорта"""
        # Старый стиль должен работать
        from fp import FreeProxy, AsyncFreeProxy, Proxy
        from fp import ProxyManager, ProxyDatabase
        from fp import ALL_SOURCES, SourceType
        
        assert FreeProxy is not None
        assert AsyncFreeProxy is not None
        assert Proxy is not None

    def test_cli_module_backward_compat(self):
        """Тест обратной совместимости CLI модуля"""
        # Старый импорт должен работать
        from fp.cli import app
        assert app is not None
