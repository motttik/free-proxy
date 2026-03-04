"""
CLI Module

Интерфейс командной строки для free-proxy
Использует typer для современного CLI с автодополнением
"""

import json
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from fp.core import FreeProxy
from fp.errors import FreeProxyException, NoWorkingProxyError

# Инициализация typer
app = typer.Typer(
    name="fp",
    help="Free Proxy CLI - получение рабочих бесплатных прокси",
    add_completion=True,
)

console = Console()


@app.command("get")
def get_proxy(
    country: Annotated[
        str | None,
        typer.Option(
            "--country", "-c",
            help="Код страны (US, GB, DE, FR, etc.) или список через запятую",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout", "-t",
            help="Таймаут проверки в секундах",
        ),
    ] = 5.0,
    randomize: Annotated[
        bool,
        typer.Option(
            "--random", "-r",
            help="Перемешать прокси перед проверкой",
        ),
    ] = False,
    anonym: Annotated[
        bool,
        typer.Option(
            "--anonym", "-a",
            help="Только анонимные прокси",
        ),
    ] = False,
    elite: Annotated[
        bool,
        typer.Option(
            "--elite", "-e",
            help="Только элитные прокси",
        ),
    ] = False,
    https: Annotated[
        bool,
        typer.Option(
            "--https",
            help="Только HTTPS прокси",
        ),
    ] = False,
    protocol: Annotated[
        str | None,
        typer.Option(
            "--protocol", "-p",
            help="Протокол (http, https, socks4, socks5)",
        ),
    ] = None,
    count: Annotated[
        int,
        typer.Option(
            "--count", "-n",
            help="Количество прокси для получения",
        ),
    ] = 1,
    output_format: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Формат вывода (txt, json, csv)",
        ),
    ] = "txt",
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Не использовать кэш",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Подробный вывод",
        ),
    ] = False,
) -> None:
    """
    Получить рабочую(ие) прокси(и)
    
    Примеры:
    
        fp get
        fp get -c US -t 1.0 -r
        fp get -n 10 -f json
        fp get -p socks5 -c DE
    """
    try:
        # Парсим страны
        country_id = None
        if country:
            country_id = [c.strip().upper() for c in country.split(",")]
        
        # Создаем клиент
        proxy_client = FreeProxy(
            country_id=country_id,
            timeout=timeout,
            rand=randomize,
            anonym=anonym,
            elite=elite,
            https=https,
            protocol=protocol,
            log_level="INFO" if verbose else "WARNING",
        )
        
        # Очищаем кэш если нужно
        if no_cache:
            proxy_client.clear_cache()
        
        # Получаем прокси
        with console.status("[bold green]Поиск рабочих прокси...[/bold green]"):
            result = proxy_client.get(count=count, repeat=True)
        
        # Выводим результат
        if output_format == "json":
            if isinstance(result, list):
                output = {"proxies": result}
            else:
                output = {"proxy": result}
            console.print(json.dumps(output, indent=2))
        
        elif output_format == "csv":
            if isinstance(result, list):
                console.print("\n".join(result))
            else:
                console.print(result)
        
        else:  # txt
            if isinstance(result, list):
                for proxy in result:
                    console.print(proxy)
            else:
                console.print(result)
        
    except NoWorkingProxyError as e:
        console.print(f"[red]Ошибка:[/red] {e.message}")
        sys.exit(1)
    
    except FreeProxyException as e:
        console.print(f"[red]Ошибка:[/red] {e.message}")
        sys.exit(1)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Отменено пользователем[/yellow]")
        sys.exit(130)


@app.command("list")
def list_sources(
    output_format: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Формат вывода (table, json)",
        ),
    ] = "table",
) -> None:
    """
    Показать список всех источников прокси
    
    Примеры:
    
        fp list
        fp list -f json
    """
    proxy_client = FreeProxy()
    sources = proxy_client.get_all_sources()
    
    if output_format == "json":
        console.print(json.dumps(sources, indent=2))
    
    else:  # table
        table = Table(title="Источники прокси")
        
        table.add_column("Название", style="cyan")
        table.add_column("Тип", style="magenta")
        table.add_column("Протоколы", style="green")
        table.add_column("Страны", style="yellow")
        table.add_column("Обновление", style="blue")
        
        for source in sources:
            protocols = ", ".join(source["protocols"])
            country = source["country"] or "Все"
            update = f"{source['update_frequency']} мин"
            
            table.add_row(
                source["name"],
                source["type"],
                protocols,
                country,
                update,
            )
        
        console.print(table)
        console.print(f"\nВсего источников: {len(sources)}")


@app.command("test")
def test_proxy(
    proxy: Annotated[
        str,
        typer.Argument(
            help="Прокси в формате IP:PORT или http://IP:PORT",
        ),
    ],
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout", "-t",
            help="Таймаут проверки в секундах",
        ),
    ] = 5.0,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Подробный вывод",
        ),
    ] = False,
) -> None:
    """
    Проверить прокси на работоспособность
    
    Примеры:
    
        fp test 1.2.3.4:8080
        fp test http://1.2.3.4:8080 -t 10
    """
    from fp.checkers.sync_checker import SyncProxyChecker
    from fp.sources.base import Proxy
    
    # Парсим прокси
    if "://" in proxy:
        protocol, rest = proxy.split("://", 1)
    else:
        protocol = "http"
        rest = proxy
    
    if ":" not in rest:
        console.print("[red]Ошибка: неверный формат прокси. Используйте IP:PORT[/red]")
        sys.exit(1)
    
    ip, port_str = rest.rsplit(":", 1)
    
    try:
        port = int(port_str)
    except ValueError:
        console.print(f"[red]Ошибка: неверный порт '{port_str}'[/red]")
        sys.exit(1)
    
    # Создаем прокси объект
    proxy_obj = Proxy(ip=ip, port=port, protocol=protocol)
    
    # Проверяем
    checker = SyncProxyChecker(timeout=timeout)
    
    with console.status(f"[bold green]Проверка {proxy}...[/bold green]"):
        is_working = checker.check(proxy_obj)
    
    if is_working:
        console.print(f"[green]✓ Прокси работает:[/green] {protocol}://{ip}:{port}")
    else:
        console.print(f"[red]✗ Прокси не работает:[/red] {protocol}://{ip}:{port}")
        sys.exit(1)


@app.command("sources")
def show_sources(
    protocol: Annotated[
        str | None,
        typer.Option(
            "--protocol", "-p",
            help="Фильтр по протоколу (http, https, socks4, socks5)",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Формат вывода (table, json)",
        ),
    ] = "table",
) -> None:
    """
    Показать доступные источники с фильтрацией
    
    Примеры:
    
        fp sources
        fp sources -p socks5
        fp sources -f json
    """
    from fp.config import ALL_SOURCES, SourceProtocol
    
    # Фильтруем по протоколу
    sources = ALL_SOURCES
    
    if protocol:
        protocol_map = {
            "http": SourceProtocol.HTTP,
            "https": SourceProtocol.HTTPS,
            "socks4": SourceProtocol.SOCKS4,
            "socks5": SourceProtocol.SOCKS5,
        }
        target = protocol_map.get(protocol.lower())
        
        if target:
            sources = [s for s in sources if target in s["protocols"]]
    
    # Вывод
    if output_format == "json":
        data = [
            {
                "name": s["name"],
                "url": s["url"],
                "type": s["type"].value,
                "protocols": [p.value for p in s["protocols"]],
            }
            for s in sources
        ]
        console.print(json.dumps(data, indent=2))
    
    else:
        table = Table(title=f"Источники ({len(sources)} шт)")
        
        table.add_column("Название", style="cyan")
        table.add_column("Тип", style="magenta")
        table.add_column("Протоколы", style="green")
        table.add_column("URL", style="dim")
        
        for source in sources:
            protocols = ", ".join(p.value for p in source["protocols"])
            
            table.add_row(
                source["name"],
                source["type"].value,
                protocols,
                source["url"][:50] + "..." if len(source["url"]) > 50 else source["url"],
            )
        
        console.print(table)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-V",
            help="Показать версию",
        ),
    ] = False,
) -> None:
    """
    Free Proxy CLI - быстрый поиск рабочих прокси
    
    Используйте 'fp COMMAND --help' для получения справки по команде.
    """
    if version:
        from fp import __version__
        console.print(f"Free Proxy CLI v{__version__}")
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
