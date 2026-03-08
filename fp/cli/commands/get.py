"""
CLI Commands - Get Proxy

Команда для получения прокси: fp get
"""

import typer
from typing import Annotated
from rich.console import Console

from fp.core import FreeProxy
from fp.errors import NoWorkingProxyError
from ..utils import (
    create_table,
    print_success,
    print_error,
    print_warning,
    format_proxy,
    format_latency,
    format_score,
    print_json,
)

console = Console()

app = typer.Typer(help="Получение прокси")


@app.command("")
def get_proxy(
    country: Annotated[
        str | None,
        typer.Option(
            "--country", "-c",
            help="Код страны (US, GB, DE, FR) или список через запятую",
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
            help="Случайный выбор прокси",
        ),
    ] = False,
    count: Annotated[
        int,
        typer.Option(
            "--count", "-n",
            help="Количество прокси для получения",
            min=1,
            max=100,
        ),
    ] = 1,
    format_output: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Формат вывода (text, json, table)",
        ),
    ] = "text",
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
) -> None:
    """
    Получить рабочие прокси

    Примеры:

        fp get
        fp get -c US -t 1.0 -r
        fp get -n 10 -f json
        fp get --https -c GB,DE
    """
    try:
        # Парсинг стран
        country_id = None
        if country:
            country_id = [c.strip().upper() for c in country.split(",")]

        # Инициализация
        proxy_client = FreeProxy(
            country_id=country_id,
            timeout=timeout,
            rand=randomize,
            https=https,
            protocol=protocol,  # type: ignore
        )

        # Получение прокси
        if count == 1:
            proxy = proxy_client.get()
            
            if format_output == "json":
                print_json({"proxy": proxy})
            elif format_output == "table":
                table = create_table("Proxy", ["Address"])
                table.add_row(format_proxy(proxy))
                console.print(table)
            else:
                print_success(f"Proxy: {proxy}")
        else:
            proxies = proxy_client.get(count=count)
            
            if format_output == "json":
                print_json({"proxies": proxies})
            elif format_output == "table":
                table = create_table(f"Proxies ({len(proxies)})", ["Address"])
                for p in proxies:
                    table.add_row(format_proxy(p))
                console.print(table)
            else:
                for p in proxies:
                    console.print(p)

    except NoWorkingProxyError:
        print_error("Нет рабочих прокси. Попробуйте увеличить таймаут или сменить страны")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Ошибка: {e}")
        raise typer.Exit(1)
