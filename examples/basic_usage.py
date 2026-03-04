#!/usr/bin/env python3
"""
Basic Example - Базовое использование FreeProxy

Простые примеры получения рабочих прокси
"""

from fp import FreeProxy


def example_1_basic():
    """Пример 1: Получить одну прокси"""
    print("=== Пример 1: Базовое использование ===")
    
    proxy = FreeProxy().get()
    print(f"Рабочая прокси: {proxy}")
    print()


def example_2_country():
    """Пример 2: Прокси из конкретной страны"""
    print("=== Пример 2: Прокси из США ===")
    
    proxy = FreeProxy(country_id=['US']).get()
    print(f"US прокси: {proxy}")
    print()


def example_3_random():
    """Пример 3: Случайная прокси"""
    print("=== Пример 3: Случайная прокси (rand=True) ===")
    
    proxy = FreeProxy(rand=True).get()
    print(f"Случайная прокси: {proxy}")
    print()


def example_4_timeout():
    """Пример 4: С таймаутом"""
    print("=== Пример 4: Быстрая проверка (timeout=0.5s) ===")
    
    proxy = FreeProxy(timeout=0.5, rand=True).get()
    print(f"Быстрая прокси: {proxy}")
    print()


def example_5_multiple():
    """Пример 5: Несколько прокси"""
    print("=== Пример 5: 5 рабочих прокси ===")
    
    proxies = FreeProxy(rand=True).get(count=5)
    
    for i, proxy in enumerate(proxies, 1):
        print(f"  {i}. {proxy}")
    print()


def example_6_filters():
    """Пример 6: С фильтрами"""
    print("=== Пример 6: Элитные HTTPS прокси ===")
    
    proxy = FreeProxy(
        elite=True,      # Только элитные
        https=True,      # Только HTTPS
        rand=True,       # Случайный выбор
    ).get()
    
    print(f"Элитная HTTPS прокси: {proxy}")
    print()


def example_7_protocol():
    """Пример 7: Выбор протокола"""
    print("=== Пример 7: SOCKS5 прокси ===")
    
    try:
        proxy = FreeProxy(protocol='socks5', rand=True).get()
        print(f"SOCKS5 прокси: {proxy}")
    except Exception as e:
        print(f"Не найдено SOCKS5 прокси: {e}")
    print()


def example_8_error_handling():
    """Пример 8: Обработка ошибок"""
    print("=== Пример 8: Обработка ошибок ===")
    
    from fp import NoWorkingProxyError
    
    try:
        # Очень строгие параметры - может не найти прокси
        proxy = FreeProxy(
            country_id=['XX'],  # Несуществующая страна
            timeout=0.1,        # Очень быстрый таймаут
        ).get()
        print(f"Найдено: {proxy}")
        
    except NoWorkingProxyError as e:
        print(f"Ошибка: {e.message}")
    print()


if __name__ == "__main__":
    print("FreeProxy - Примеры использования\n")
    print("=" * 50)
    print()
    
    # Запускаем примеры
    example_1_basic()
    example_2_country()
    example_3_random()
    example_4_timeout()
    example_5_multiple()
    example_6_filters()
    example_7_protocol()
    example_8_error_handling()
    
    print("=" * 50)
    print("Все примеры завершены!")
