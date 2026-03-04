"""
CLI Module

Интерфейс командной строки для free-proxy
Использует typer для современного CLI с автодополнением
"""

import json
import sys
import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from fp.core import FreeProxy
from fp.errors import FreeProxyException, NoWorkingProxyError
from fp.database import ProxyDatabase
from fp.pipeline import ProxyPipeline
from fp.source_health import SourceHealthManager
from fp.slo_monitor import SLOMonitor

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


# ============================================================================
# OPERATOR CLI COMMANDS (v3.1)
# ============================================================================

operator_app = typer.Typer(name="operator", help="Operator commands for pool management")
app.add_typer(operator_app, name="op")


@operator_app.command("discover")
def discover_sources(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results from GitHub")] = 50,
):
    """Search for new proxy sources on GitHub"""
    
    async def _run():
        from fp.github_discovery import GitHubDiscovery
        
        async with GitHubDiscovery(max_results=limit) as discovery:
            console.print("[bold cyan]Searching for new sources on GitHub...[/bold cyan]")
            new_sources = await discovery.discover_new_sources()
            
            stats = discovery.get_discovery_stats()
            console.print(f"\nDiscovered [bold green]{stats['total_discovered']}[/bold green] sources")
            
            if stats["sources"]:
                table = Table(title="Top Candidates")
                table.add_column("Source Name", style="cyan")
                table.add_column("Repo", style="magenta")
                table.add_column("Status", style="green")
                
                for s in stats["sources"][:10]:
                    table.add_row(s["name"], s["repo"], s["status"])
                
                console.print(table)
                
    asyncio.run(_run())

@operator_app.command("status")
def pool_status():
    """Pool status: HOT/WARM/QUARANTINE统计"""
    
    async def _run():
        async with ProxyDatabase() as db:
            stats = await db.get_stats()
            
            console.print("[bold]Proxy Pool Status[/bold]\n")
            
            # Table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Pool", style="cyan")
            table.add_column("Count", justify="right")
            table.add_column("Target", justify="right")
            table.add_column("Status", style="green")
            
            # HOT
            hot_target = 30
            hot_status = "✓ OK" if stats["hot_count"] >= 20 else "⚠ LOW" if stats["hot_count"] >= 10 else "✗ CRITICAL"
            table.add_row("HOT", str(stats["hot_count"]), str(hot_target), hot_status)
            
            # WARM
            table.add_row("WARM", str(stats["warm_count"]), "-", "✓")
            
            # QUARANTINE
            table.add_row("QUARANTINE", str(stats["quarantine_count"]), "-", "✓")
            
            # TOTAL
            table.add_row("TOTAL", str(stats["total_proxies"]), "-", "✓")
            
            console.print(table)
            
            # Stats
            console.print(f"\n[bold]Avg Score:[/bold] {stats['avg_score']:.1f}")
            console.print(f"[bold]Checks 24h:[/bold] {stats['checks_24h']} ({stats['success_24h']} successful)")
            console.print(f"[bold]Banlist:[/bold] {stats['banlist_count']} IPs")
    
    asyncio.run(_run())


@operator_app.command("source-health")
def source_health():
    """Source health: pass rate, fail streak, disabled sources"""
    
    async def _run():
        async with SourceHealthManager() as manager:
            stats = manager.get_stats()
            
            console.print("[bold]Source Health[/bold]\n")
            
            # Summary
            console.print(f"Total: {stats['total_sources']} | Available: {stats['available']} | Disabled: {stats['disabled']}")
            console.print(f"Avg Pass Rate: {stats['avg_pass_rate']:.1f}%\n")
            
            # Top errors
            if stats["top_errors"]:
                console.print("[bold red]Top Errors:[/bold red]")
                for error, count in stats["top_errors"]:
                    console.print(f"  {error}: {count}")
                console.print()
            
            # Disabled sources
            disabled = manager.get_disabled_sources()
            if disabled:
                console.print("[bold red]Disabled Sources:[/bold red]")
                table = Table(show_header=True, header_style="bold red")
                table.add_column("Name", style="cyan")
                table.add_column("Fail Streak", justify="right")
                table.add_column("Pass Rate", justify="right")
                table.add_column("Until", style="yellow")
                
                for source in disabled[:10]:
                    table.add_row(
                        source["name"],
                        str(source["fail_streak"]),
                        f"{source['pass_rate']:.1f}%",
                        source["disabled_until"].split("T")[0],
                    )
                
                console.print(table)
    
    asyncio.run(_run())


@operator_app.command("alerts")
def slo_alerts():
    """SLO alerts: active alerts and summary"""
    
    async def _run():
        async with SLOMonitor() as monitor:
            await monitor.check_slo()
            summary = monitor.get_alert_summary()
            
            console.print("[bold]SLO Alerts[/bold]\n")
            console.print(f"Total: {summary['total']} | Critical: {summary['critical']} | Warning: {summary['warning']} | Info: {summary['info']}\n")
            
            if summary["alerts"]:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Severity", style="cyan")
                table.add_column("Message")
                table.add_column("Since", style="yellow")
                
                for alert in summary["alerts"]:
                    severity_style = "bold red" if alert["severity"] == "critical" else "bold yellow" if alert["severity"] == "warning" else "green"
                    since = alert["timestamp"].split("T")[1].split(".")[0]
                    table.add_row(
                        f"[{severity_style}]{alert['severity'].upper()}[/{severity_style}]",
                        alert["message"],
                        since,
                    )
                
                console.print(table)
            else:
                console.print("[green]✓ No active alerts[/green]")
    
    asyncio.run(_run())


@operator_app.command("rebuild-hot")
def rebuild_hot_pool(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max proxies to recheck")] = 100,
):
    """Rebuild HOT pool: recheck quarantine proxies"""
    
    async def _run():
        from fp.manager import ProxyManager
        
        async with ProxyManager() as manager:
            console.print(f"[bold]Rebuilding HOT pool (limit: {limit})...[/bold]\n")
            
            report = await manager.refresh_quarantine(limit=limit)
            
            console.print(f"Total: {report['total']}")
            console.print(f"[green]Upgraded:[/green] {report['upgraded']}")
            console.print(f"[red]Still Bad:[/red] {report['still_bad']}")
    
    asyncio.run(_run())


@operator_app.command("explain")
def explain_proxy(
    ip: Annotated[str, typer.Argument(help="Proxy IP")],
    port: Annotated[int, typer.Argument(help="Proxy port")],
):
    """Explain proxy: почему в HOT/WARM/QUARANTINE"""
    
    async def _run():
        async with ProxyDatabase() as db:
            proxy_id = await db.get_proxy_id(ip, port, "http")
            
            if not proxy_id:
                console.print(f"[red]Proxy {ip}:{port} not found[/red]")
                return
            
            # Get metrics
            cursor = await db._conn.execute(
                "SELECT pool, score, latency_ms, uptime, success_rate, ban_rate FROM proxies p JOIN metrics m ON p.id = m.proxy_id WHERE p.id = ?",
                (proxy_id,),
            )
            row = await cursor.fetchone()
            
            if not row:
                console.print("[red]No data[/red]")
                return
            
            pool, score, latency, uptime, success_rate, ban_rate = row
            
            console.print(f"[bold]Proxy {ip}:{port}[/bold]\n")
            
            # Pool badge
            pool_badge = "🟢 HOT" if pool == "hot" else "🟡 WARM" if pool == "warm" else "🔴 QUARANTINE"
            console.print(f"Pool: {pool_badge}")
            console.print(f"Score: {score:.1f}/100")
            
            # Metrics
            table = Table(show_header=False, box=None)
            table.add_column("Metric", style="cyan")
            table.add_column("Value")
            
            table.add_row("Latency", f"{latency:.0f}ms")
            table.add_row("Uptime", f"{uptime:.1f}%")
            table.add_row("Success Rate", f"{success_rate:.1f}%")
            table.add_row("Ban Rate", f"{ban_rate:.1f}%")
            
            console.print(table)
            
            # Explanation
            console.print("\n[bold]Explanation:[/bold]")
            if pool == "hot":
                console.print("✓ High score, reliable proxy")
            elif pool == "warm":
                console.print("⚠ Moderate score, needs more validation")
            else:
                console.print(f"✗ Low score ({score:.1f}). Reasons:")
                if uptime < 50:
                    console.print(f"  - Low uptime ({uptime:.1f}%)")
                if success_rate < 50:
                    console.print(f"  - Low success rate ({success_rate:.1f}%)")
                if ban_rate > 20:
                    console.print(f"  - High ban rate ({ban_rate:.1f}%)")
                if latency > 2000:
                    console.print(f"  - High latency ({latency:.0f}ms)")
    
    asyncio.run(_run())


@operator_app.command("get")
def op_get_proxy(
    profile: Annotated[str, typer.Option("--profile", help="Профиль: universal, speed-first, stability-first")] = "universal",
    country: Annotated[str | None, typer.Option("--country", "-c", help="Код страны")] = None,
    protocol: Annotated[str | None, typer.Option("--protocol", "-p", help="Протокол")] = None,
    min_score: Annotated[float, typer.Option("--min-score", help="Минимальный score")] = 50.0,
):
    """Get best proxy from pool by profile"""
    
    async def _run():
        from fp.manager import ProxyManager
        
        async with ProxyManager() as manager:
            proxy = await manager.get_proxy(
                country=country,
                protocol=protocol,
                min_score=min_score,
                profile=profile,
            )
            
            if proxy:
                console.print(f"[bold green]✓ Found Proxy ({profile})[/bold green]")
                console.print(f"URL: {proxy['protocol']}://{proxy['ip']}:{proxy['port']}")
                console.print(f"Score: {proxy['score']:.1f}/100")
                console.print(f"Latency: {proxy['latency_ms']:.0f}ms")
                console.print(f"Uptime: {proxy.get('uptime', 100):.1f}%")
                console.print(f"Country: {proxy['country']}")
            else:
                console.print("[red]✗ No suitable proxy found in pool[/red]")
                
    asyncio.run(_run())

@operator_app.command("run-pipeline")
def run_pipeline(
    skip_targeted: Annotated[bool, typer.Option("--skip-targeted", help="Skip Stage B validation")] = False,
):
    """Run full pipeline cycle"""
    
    async def _run():
        async with ProxyPipeline(max_concurrent=50) as pipeline:
            console.print("[bold]Running Pipeline Cycle...[/bold]\n")
            
            report = await pipeline.run_cycle(skip_targeted=skip_targeted)
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Stage", style="cyan")
            table.add_column("Count", justify="right")
            
            table.add_row("Collected", str(report.collected))
            table.add_row("Deduped", str(report.deduped))
            table.add_row("Validated Fast", str(report.validated_fast))
            table.add_row("Validated Targeted", str(report.validated_targeted))
            table.add_row("HOT", f"[green]{report.hot_count}[/green]")
            table.add_row("WARM", f"[yellow]{report.warm_count}[/yellow]")
            table.add_row("Quarantine", f"[red]{report.quarantine_count}[/red]")
            
            console.print(table)
            
            console.print(f"\n[bold]Avg Score:[/bold] {report.avg_score:.1f}")
            console.print(f"[bold]Avg Latency:[/bold] {report.avg_latency:.0f}ms")

            if report.top_fail_reasons:
                console.print("\n[bold red]Top Fail Reasons:[/bold red]")
                for reason, count in sorted(report.top_fail_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                    console.print(f"  {reason}: {count}")

    asyncio.run(_run())


# ============================================================================
# SMOKE TEST COMMAND (v3.3)
# ============================================================================

@operator_app.command("smoke")
def smoke_test_cmd(
    n: Annotated[int, typer.Option("--n", "-n", help="Number of proxies to test")] = 10,
    url: Annotated[str, typer.Option("--url", "-u", help="Test URL")] = "https://httpbin.org/ip",
    timeout: Annotated[float, typer.Option("--timeout", "-t", help="Timeout in seconds")] = 10.0,
    use_quarantine: Annotated[bool, typer.Option("--use-quarantine", help="Use quarantine proxies")] = False,
):
    """
    Smoke test: проверить N прокси реальным запросом
    
    Пример:
        fp op smoke -n 10 --url https://httpbin.org/ip
    """
    from fp.smoke import smoke_test, print_report
    
    async def _run():
        results = await smoke_test(
            n=n,
            test_url=url,
            timeout=timeout,
            use_quarantine=use_quarantine,
        )
        print_report(results)
        
        # Exit code
        if results["ratio"] < 0.3:
            raise typer.Exit(code=1)
    
    asyncio.run(_run())
