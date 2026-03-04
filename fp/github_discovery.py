"""
GitHub Auto-Discovery Module

Автоматический поиск новых источников прокси:
- GitHub API search по proxy-list паттернам
- Проверка candidate sources в sandbox
- Auto-promote при pass_rate > 40%
- Auto-disable при pass_rate < 20%
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx

from fp.config import ProxySource, SourceType, SourceProtocol
from fp.source_health import SourceHealthManager


@dataclass
class DiscoveredSource:
    """Найденный источник"""
    name: str
    url: str
    repo: str
    path: str
    discovered_at: float = field(default_factory=time.time)
    sandbox_cycles: int = 0
    pass_rate: float = 100.0
    status: Literal["candidate", "promoted", "disabled"] = "candidate"


class GitHubDiscovery:
    """
    GitHub Auto-Discovery
    
    Ищет репозитории с proxy lists:
    - proxy-list
    - free-proxy
    - proxy*.txt
    - http.txt
    - socks.txt
    """
    
    # GitHub API endpoint
    GITHUB_API = "https://api.github.com"
    
    # Search queries
    SEARCH_QUERIES = [
        "proxy-list",
        "free-proxy",
        "proxy scraper",
        "proxy collection",
        "http proxy list",
        "socks proxy list",
    ]
    
    # File patterns для proxy lists
    FILE_PATTERNS = [
        "proxy*.txt",
        "http*.txt",
        "https*.txt",
        "socks*.txt",
        "proxies.txt",
    ]
    
    # Whitelist проверенных авторов
    TRUSTED_AUTHORS = [
        "TheSpeedX",
        "monosans",
        "clarketm",
        "Sunny9577",
        "JetKai",
        "ShiftyTR",
        "miyukii-chan",
        "roosterkid",
    ]
    
    def __init__(
        self,
        github_token: str | None = None,
        max_results: int = 50,
    ) -> None:
        self.github_token = github_token
        self.max_results = max_results
        self._client: httpx.AsyncClient | None = None
        self._health_manager: SourceHealthManager | None = None
        self._discovered: dict[str, DiscoveredSource] = {}
    
    async def __aenter__(self) -> "GitHubDiscovery":
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "FreeProxy-Discovery/3.1",
        }
        
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
        )
        
        self._health_manager = SourceHealthManager()
        await self._health_manager.__aenter__()
        
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
        if self._health_manager:
            await self._health_manager.__aexit__(*args)
    
    async def search_repositories(self) -> list[dict]:
        """Поиск репозиториев с proxy lists"""
        if not self._client:
            return []
        
        all_repos = []
        
        for query in self.SEARCH_QUERIES:
            try:
                response = await self._client.get(
                    f"{self.GITHUB_API}/search/repositories",
                    params={
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": min(self.max_results // len(self.SEARCH_QUERIES), 10),
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    all_repos.extend(data.get("items", []))
                    
            except Exception as e:
                pass
        
        # Dedup по full_name
        seen = set()
        unique_repos = []
        
        for repo in all_repos:
            if repo["full_name"] not in seen:
                seen.add(repo["full_name"])
                unique_repos.append(repo)
        
        return unique_repos[:self.max_results]
    
    async def find_proxy_files(self, repo_full_name: str) -> list[str]:
        """Найти proxy файлы в репозитории"""
        if not self._client:
            return []
        
        owner, repo = repo_full_name.split("/", 1)
        proxy_files = []
        
        try:
            # Получаем содержимое root
            response = await self._client.get(
                f"{self.GITHUB_API}/repos/{owner}/{repo}/contents",
            )
            
            if response.status_code == 200:
                contents = response.json()
                
                for item in contents:
                    if item["type"] == "file":
                        # Проверка паттернов
                        for pattern in self.FILE_PATTERNS:
                            regex = pattern.replace("*", ".*")
                            if re.match(regex, item["name"], re.IGNORECASE):
                                proxy_files.append(item["path"])
                                break
                        
                        # Проверка по имени
                        if any(kw in item["name"].lower() for kw in ["proxy", "http", "socks"]):
                            if item["path"] not in proxy_files:
                                proxy_files.append(item["path"])
            
        except Exception:
            pass
        
        return proxy_files[:20]  # Максимум 20 файлов
    
    def create_source_from_file(
        self,
        repo_full_name: str,
        file_path: str,
    ) -> ProxySource:
        """Создать ProxySource из GitHub файла"""
        url = f"https://raw.githubusercontent.com/{repo_full_name}/master/{file_path}"
        
        # Определяем протокол по имени файла
        protocols = [SourceProtocol.HTTP]
        file_lower = file_path.lower()
        
        if "socks5" in file_lower:
            protocols = [SourceProtocol.SOCKS5]
        elif "socks4" in file_lower:
            protocols = [SourceProtocol.SOCKS4]
        elif "https" in file_lower:
            protocols = [SourceProtocol.HTTPS]
        
        return ProxySource(
            name=f"GitHub/{repo_full_name}/{file_path}",
            url=url,
            type=SourceType.GITHUB_RAW,
            protocols=protocols,
            country=None,
            update_frequency=60,
            timeout=30,
            max_retries=3,
        )
    
    async def discover_new_sources(self) -> list[DiscoveredSource]:
        """Полный цикл discovery"""
        discovered = []
        
        # 1. Поиск репозиториев
        repos = await self.search_repositories()
        
        # 2. Поиск proxy файлов
        for repo in repos:
            repo_name = repo["full_name"]
            
            # Пропускаем trusted авторов (уже есть в конфиге)
            author = repo_name.split("/")[0]
            if author in self.TRUSTED_AUTHORS:
                continue
            
            proxy_files = await self.find_proxy_files(repo_name)
            
            for file_path in proxy_files:
                source = self.create_source_from_file(repo_name, file_path)
                
                # Проверка, есть ли уже в health manager
                if self._health_manager and source["url"] in self._health_manager.sources:
                    continue
                
                # Создаём discovered source
                discovered_source = DiscoveredSource(
                    name=source["name"],
                    url=source["url"],
                    repo=repo_name,
                    path=file_path,
                )
                
                self._discovered[source["url"]] = discovered_source
                discovered.append(discovered_source)
        
        return discovered
    
    async def sandbox_test(self, source_url: str) -> bool:
        """
        Sandbox test для candidate source
        
        Returns:
            True если pass_rate > 20%
        """
        if not self._health_manager:
            return False
        
        # Проверяем доступность
        if not self._health_manager.is_available(source_url):
            return False
        
        # В реальности здесь был бы вызов parser.parse()
        # Для демо просто increment sandbox_cycles
        if source_url in self._discovered:
            self._discovered[source_url].sandbox_cycles += 1
            
            # После 3 циклов проверяем pass_rate
            if self._discovered[source_url].sandbox_cycles >= 3:
                health = self._health_manager.sources.get(source_url)
                if health:
                    self._discovered[source_url].pass_rate = health.pass_rate
                    
                    # Auto-promote/disabled
                    if health.pass_rate > 40:
                        self._discovered[source_url].status = "promoted"
                        return True
                    elif health.pass_rate < 20:
                        self._discovered[source_url].status = "disabled"
                        return False
        
        return True  # Продолжаем sandbox test
    
    def get_promoted_sources(self) -> list[ProxySource]:
        """Получить promoted sources для добавления в конфиг"""
        promoted = []
        
        for source in self._discovered.values():
            if source.status == "promoted":
                protocols = [SourceProtocol.HTTP]
                if "socks5" in source.path.lower():
                    protocols = [SourceProtocol.SOCKS5]
                elif "socks4" in source.path.lower():
                    protocols = [SourceProtocol.SOCKS4]
                
                promoted.append(ProxySource(
                    name=source.name,
                    url=source.url,
                    type=SourceType.GITHUB_RAW,
                    protocols=protocols,
                    country=None,
                    update_frequency=60,
                    timeout=30,
                    max_retries=3,
                ))
        
        return promoted
    
    def get_discovery_stats(self) -> dict:
        """Статистика discovery"""
        total = len(self._discovered)
        candidate = sum(1 for s in self._discovered.values() if s.status == "candidate")
        promoted = sum(1 for s in self._discovered.values() if s.status == "promoted")
        disabled = sum(1 for s in self._discovered.values() if s.status == "disabled")
        
        return {
            "total_discovered": total,
            "candidate": candidate,
            "promoted": promoted,
            "disabled": disabled,
            "sources": [
                {
                    "name": s.name,
                    "repo": s.repo,
                    "status": s.status,
                    "pass_rate": s.pass_rate,
                    "sandbox_cycles": s.sandbox_cycles,
                }
                for s in list(self._discovered.values())[:20]
            ],
        }


async def main():
    """Пример использования"""
    async with GitHubDiscovery() as discovery:
        print("=== GitHub Discovery ===")
        discovered = await discovery.discover_new_sources()
        print(f"Discovered: {len(discovered)} new sources")
        
        stats = discovery.get_discovery_stats()
        print(f"\nStats: {stats['total_discovered']} total")
        print(f"  Candidate: {stats['candidate']}")
        print(f"  Promoted: {stats['promoted']}")
        print(f"  Disabled: {stats['disabled']}")
        
        if stats["sources"]:
            print("\nTop Sources:")
            for source in stats["sources"][:5]:
                print(f"  {source['name']} ({source['status']}) - {source['pass_rate']:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
