"""
CLI Utilities

Утилиты для CLI: таблицы, цвета, форматирование
"""

from rich.console import Console
from rich.table import Table
from typing import Any

console = Console()


def create_table(title: str, columns: list[str]) -> Table:
    """Создать таблицу с заголовком"""
    table = Table(
        title=title,
        show_header=True,
        header_style="bold magenta",
        border_style="blue",
    )
    for col in columns:
        table.add_column(col)
    return table


def print_success(message: str) -> None:
    """Вывести сообщение об успехе"""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Вывести сообщение об ошибке"""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Вывести предупреждение"""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Вывести информацию"""
    console.print(f"[blue]ℹ[/blue] {message}")


def format_proxy(proxy: str) -> str:
    """Форматировать прокси для вывода"""
    if proxy.startswith('http://'):
        return f"[green]{proxy}[/green]"
    elif proxy.startswith('https://'):
        return f"[cyan]{proxy}[/cyan]"
    elif 'socks4' in proxy:
        return f"[yellow]{proxy}[/yellow]"
    elif 'socks5' in proxy:
        return f"[magenta]{proxy}[/magenta]"
    return proxy


def format_latency(ms: float) -> str:
    """Форматировать задержку с цветом"""
    if ms < 100:
        return f"[green]{ms:.0f}ms[/green]"
    elif ms < 500:
        return f"[yellow]{ms:.0f}ms[/yellow]"
    else:
        return f"[red]{ms:.0f}ms[/red]"


def format_score(score: float) -> str:
    """Форматировать score с цветом"""
    if score >= 80:
        return f"[green]{score:.1f}[/green]"
    elif score >= 50:
        return f"[yellow]{score:.1f}[/yellow]"
    else:
        return f"[red]{score:.1f}[/red]"


def print_json(data: Any) -> None:
    """Вывести JSON с подсветкой"""
    import json
    console.print_json(json.dumps(data, indent=2, ensure_ascii=False))
