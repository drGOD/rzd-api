from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Config:
    """Runtime configuration for the RZD client."""

    language: str = "ru"
    base_url: str = "https://ticket.rzd.ru/api/v1"
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    retry_total: int = 3
    retry_backoff: float = 0.5
    station_cache_ttl: float = 3600.0
    station_cache_size: int = 256
    proxy: str | None = None
    user_agent: str | None = None
    referer: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.language, str) or self.language not in {"ru", "en"}:
            raise ValueError("language must be either 'ru' or 'en'.")
        if not isinstance(self.base_url, str) or not self.base_url.startswith(
            ("http://", "https://")
        ):
            raise ValueError("base_url must be an absolute HTTP(S) URL.")
        if not self._is_number(self.connect_timeout) or not self._is_number(self.read_timeout):
            raise ValueError("connect_timeout and read_timeout must be numbers.")
        if self.connect_timeout <= 0 or self.read_timeout <= 0:
            raise ValueError("connect_timeout and read_timeout must be positive.")
        if isinstance(self.retry_total, bool) or not isinstance(self.retry_total, int):
            raise ValueError("retry_total must be an integer.")
        if not self._is_number(self.retry_backoff):
            raise ValueError("retry_backoff must be a number.")
        if self.retry_total < 0 or self.retry_backoff < 0:
            raise ValueError("retry_total and retry_backoff must not be negative.")
        if not self._is_number(self.station_cache_ttl):
            raise ValueError("station_cache_ttl must be a number.")
        if isinstance(self.station_cache_size, bool) or not isinstance(
            self.station_cache_size, int
        ):
            raise ValueError("station_cache_size must be an integer.")
        if self.station_cache_ttl < 0 or self.station_cache_size < 0:
            raise ValueError("station cache settings must not be negative.")
        for name in ("proxy", "user_agent", "referer"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None.")

    @staticmethod
    def _is_number(value: object) -> bool:
        return not isinstance(value, bool) and isinstance(value, (int, float))
