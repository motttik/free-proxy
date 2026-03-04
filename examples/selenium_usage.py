#!/usr/bin/env python3
"""
Selenium Example - Использование с Selenium

Интеграция FreeProxy с Selenium для веб-скрапинга
"""

from fp import FreeProxy
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def get_selenium_driver_with_proxy(proxy: str):
    """
    Создать Selenium WebDriver с прокси
    
    Args:
        proxy: прокси в формате "IP:PORT" или "http://IP:PORT"
    
    Returns:
        Selenium WebDriver
    """
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Настраиваем прокси
    chrome_options.add_argument(f'--proxy-server={proxy}')
    
    return webdriver.Chrome(options=chrome_options)


def example_1_basic():
    """Пример 1: Базовое использование с Selenium"""
    print("=== Пример 1: Selenium с прокси ===")
    
    # Получаем рабочую прокси
    proxy = FreeProxy(country_id=['US'], timeout=2.0).get()
    print(f"Используем прокси: {proxy}")
    
    try:
        # Создаем драйвер с прокси
        driver = get_selenium_driver_with_proxy(proxy)
        
        # Открываем страницу
        driver.get('https://httpbin.org/ip')
        
        # Получаем IP
        ip_element = driver.find_element('css selector', 'code')
        print(f"Ваш IP: {ip_element.text}")
        
        driver.quit()
        
    except Exception as e:
        print(f"Ошибка: {e}")
    
    print()


def example_2_rotate_proxies():
    """Пример 2: Ротация прокси для множества запросов"""
    print("=== Пример 2: Ротация прокси ===")
    
    urls = [
        'https://httpbin.org/ip',
        'https://api.ipify.org',
        'https://ifconfig.me',
    ]
    
    for url in urls:
        try:
            # Новая прокси для каждого запроса
            proxy = FreeProxy(rand=True, timeout=2.0).get()
            print(f"\nЗапрос к {url} через {proxy}")
            
            driver = get_selenium_driver_with_proxy(proxy)
            driver.get(url)
            
            print(f"  Ответ: {driver.title}")
            driver.quit()
            
        except Exception as e:
            print(f"  Ошибка: {e}")
    
    print()


def example_3_retry_on_failure():
    """Пример 3: Повтор с новой прокси при ошибке"""
    print("=== Пример 3: Повтор с новой прокси ===")
    
    target_url = 'https://httpbin.org/ip'
    max_attempts = 5
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Попытка {attempt}/{max_attempts}...")
            
            proxy = FreeProxy(timeout=2.0, rand=True).get()
            print(f"  Прокси: {proxy}")
            
            driver = get_selenium_driver_with_proxy(proxy)
            driver.get(target_url)
            
            print(f"  ✓ Успех!")
            driver.quit()
            break
            
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            
            if attempt == max_attempts:
                print("  Превышено количество попыток")
            else:
                print("  Пробуем другую прокси...")
    
    print()


def example_4_with_requests():
    """Пример 4: Использование с requests (альтернатива Selenium)"""
    print("=== Пример 4: Использование с requests ===")
    
    import requests
    
    # Получаем прокси
    proxy_str = FreeProxy(timeout=2.0).get()
    print(f"Прокси: {proxy_str}")
    
    # Парсим прокси
    if '://' in proxy_str:
        protocol, rest = proxy_str.split('://', 1)
    else:
        protocol = 'http'
        rest = proxy_str
    
    proxies = {
        'http': proxy_str,
        'https': proxy_str,
    }
    
    try:
        response = requests.get(
            'https://httpbin.org/ip',
            proxies=proxies,
            timeout=5,
        )
        
        data = response.json()
        print(f"IP через прокси: {data.get('origin')}")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    
    print()


if __name__ == "__main__":
    print("FreeProxy + Selenium - Примеры использования\n")
    print("=" * 50)
    print()
    
    # Внимание: для примеров нужен Selenium
    try:
        example_1_basic()
        example_2_rotate_proxies()
        example_3_retry_on_failure()
        example_4_with_requests()
        
    except ImportError as e:
        print(f"Требуется установка: pip install selenium")
        print(f"Ошибка: {e}")
    
    print("=" * 50)
    print("Примеры завершены!")
