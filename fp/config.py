"""
Free Proxy Configuration

Централизованная конфигурация для v3.2+
"""

from dataclasses import dataclass


@dataclass
class HealthConfig:
    """Health contract конфигурация"""
    
    # TTL для пулов (минуты)
    hot_ttl_minutes: int = 15  # HOT прокси действителен 15 минут
    warm_ttl_minutes: int = 45  # WARM прокси действителен 45 минут
    
    # Пороги для HOT
    hot_min_score: float = 80  # Минимальный score для HOT
    hot_max_latency_ms: float = 1000  # Максимальная latency для HOT (1 сек)
    hot_require_live_check: bool = True  # Требовать live-check для HOT
    
    # Пороги для WARM
    warm_min_score: float = 50  # Минимальный score для WARM
    
    # Auto-downgrade
    auto_downgrade_on_fail: bool = True  # Auto-downgrade при fail
    fail_streak_threshold: int = 3  # Количество fail для downgrade
    
    # Revalidation
    revalidate_before_expire_minutes: int = 5  # Перепроверять за 5 мин до истечения TTL


@dataclass
class ValidationConfig:
    """Конфигурация валидации"""
    
    # Stage A
    stage_a_timeout: float = 3.0
    stage_a_url: str = "https://httpbin.org/ip"
    stage_a_skip_ip_match_for_github: bool = True  # Пропускать IP match для GitHub Raw
    
    # Stage B
    stage_b_timeout: float = 7.0
    stage_b_target_domains: list = None
    
    def __post_init__(self):
        if self.stage_b_target_domains is None:
            self.stage_b_target_domains = [
                "https://www.google.com",
                "https://httpbin.org/ip",
            ]


@dataclass
class SelectionConfig:
    """Конфигурация выбора прокси"""
    
    # Rotation
    enable_rotation: bool = True  # Включить rotation
    rotation_window: int = 10  # Не повторять прокси в последних N выдачах
    
    # Diversity
    enable_diversity: bool = True  # Включить diversity
    max_same_subnet: int = 2  # Максимум прокси из одной /24 подсети
    
    # Filtering
    exclude_recent_fail_minutes: int = 10  # Исключать прокси с fail за последние N минут
    min_checks_for_selection: int = 1  # Минимальное количество проверок для выбора


# Глобальные конфиги
health = HealthConfig()
validation = ValidationConfig()
selection = SelectionConfig()
