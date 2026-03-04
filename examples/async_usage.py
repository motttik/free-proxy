#!/usr/bin/env python3
"""
Async Example - Асинхронное использование FreeProxy

Быстрая параллельная проверка прокси с использованием asyncio
"""

import asyncio
from fp import AsyncFreeProxy


async def example_1_basic():
    """Пример 1: Базовое асинхронное использование"""
    print("=== Пример 1: Async базовое ===")
    
    proxy = await AsyncFreeProxy().get()
    print(f"Рабочая прокси: {proxy}")
    print()


async def example_2_multiple():
    """Пример 2: Получить несколько прокси"""
    print("=== Пример 2: 10 прокси асинхронно ===")
    
    # Асинхронная проверка 100 прокси занимает ~10 секунд вместо ~50
    proxies = await AsyncFreeProxy(rand=True).get(count=10, show_progress=True)
    
    print(f"\nНайдено {len(proxies)} рабочих прокси:")
    for i, proxy in enumerate(proxies, 1):
        print(f"  {i}. {proxy}")
    print()


async def example_3_concurrent():
    """Пример 3: Настройка параллелизма"""
    print("=== Пример 3: 50 одновременных проверок ===")
    
    afp = AsyncFreeProxy(
        max_concurrent=50,  # Увеличиваем параллелизм
        timeout=3.0,        # Увеличиваем таймаут
        rand=True,
    )
    
    proxies = await afp.get(count=5)
    
    for i, proxy in enumerate(proxies, 1):
        print(f"  {i}. {proxy}")
    print()


async def example_4_protocol():
    """Пример 4: Выбор протокола"""
    print("=== Пример 4: HTTP прокси ===")
    
    afp = AsyncFreeProxy(protocol='http', rand=True)
    
    proxy = await afp.get()
    print(f"HTTP прокси: {proxy}")
    print()


async def example_5_country():
    """Пример 5: Прокси из конкретной страны"""
    print("=== Пример 5: Прокси из Германии ===")
    
    afp = AsyncFreeProxy(
        country_id=['DE'],
        timeout=2.0,
        rand=True,
    )
    
    try:
        proxy = await afp.get()
        print(f"DE прокси: {proxy}")
    except Exception as e:
        print(f"Не найдено прокси из Германии: {e}")
    print()


async def example_6_check_single():
    """Пример 6: Проверка одной прокси"""
    print("=== Пример 6: Быстрая проверка IP:PORT ===")
    
    afp = AsyncFreeProxy()
    
    # Проверяем конкретную прокси
    is_working = await afp.check_proxy('8.219.97.248', 80)
    
    if is_working:
        print("✓ Прокси работает: 8.219.97.248:80")
    else:
        print("✗ Прокси не работает: 8.219.97.248:80")
    print()


async def example_7_cache():
    """Пример 7: Использование кэша"""
    print("=== Пример 7: Кэширование результатов ===")
    
    afp = AsyncFreeProxy(cache_ttl=600)  # 10 минут кэш
    
    # Первый запрос - проверка
    print("Первый запрос (проверка)...")
    proxy1 = await afp.get()
    print(f"  Найдено: {proxy1}")
    
    # Второй запрос - из кэша
    print("Второй запрос (из кэша)...")
    proxy2 = await afp.get()
    print(f"  Найдено: {proxy2}")
    
    # Очищаем кэш
    afp.clear_cache()
    print("Кэш очищен")
    print()


async def example_8_batch():
    """Пример 8: Массовая проверка"""
    print("=== Пример 8: Массовая проверка (100 прокси) ===")
    
    import time
    
    afp = AsyncFreeProxy(
        max_concurrent=30,
        timeout=5.0,
        rand=True,
    )
    
    start = time.time()
    
    proxies = await afp.get(count=20, show_progress=False)
    
    elapsed = time.time() - start
    
    print(f"\n⏱ Время: {elapsed:.2f} сек")
    print(f"✓ Найдено {len(proxies)} рабочих прокси")
    print()


async def main():
    """Запуск всех примеров"""
    print("AsyncFreeProxy - Примеры использования\n")
    print("=" * 50)
    print()
    
    await example_1_basic()
    await example_2_multiple()
    await example_3_concurrent()
    await example_4_protocol()
    await example_5_country()
    await example_6_check_single()
    await example_7_cache()
    await example_8_batch()
    
    print("=" * 50)
    print("Все примеры завершены!")


if __name__ == "__main__":
    asyncio.run(main())
