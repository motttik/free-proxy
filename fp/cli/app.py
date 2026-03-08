"""
CLI Application

Главное приложение Typer с регистрацией команд
"""

import typer
from rich.console import Console

from .commands.get import app as get_app
from .utils import print_info, print_success

console = Console()

# Основное приложение
app = typer.Typer(
    name="fp",
    help="Free Proxy CLI - получение рабочих бесплатных прокси",
    add_completion=True,
)

# Регистрация команд
app.add_typer(get_app, name="get")


@app.command("version")
def version() -> None:
    """Показать версию"""
    from fp import __version__
    print_success(f"Free Proxy v{__version__}")


@app.command("info")
def info() -> None:
    """Показать информацию о проекте"""
    print_info("Free Proxy - инструмент для получения бесплатных прокси")
    print_info("Источники: 53+ (GitHub, API, HTML)")
    print_info("Протоколы: HTTP, HTTPS, SOCKS4, SOCKS5")
    console.print("\n[bold]Команды:[/bold]")
    console.print("  fp get     - Получить прокси")
    console.print("  fp version - Показать версию")
    console.print("  fp info    - Показать информацию")


if __name__ == "__main__":
    app()
