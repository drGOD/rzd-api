# Changelog

## 2.0.0 — 2026-07-19

### Breaking changes

- Единый типизированный `RzdClient`; удалены публичные `Api`, `Query` и JSON-методы.
- Методы возвращают dataclass-модели вместо необработанных `dict`/JSON-строк.
- Удалены legacy-имена параметров и MCP SSE transport.
- MCP tools переименованы и возвращают structured content.
- `Config.timeout` заменён на `connect_timeout` и `read_timeout`.

### Fixed

- Обратный маршрут меняет origin и destination местами.
- HTTP MCP совместим с MCP SDK 1.28 и корректно использует host/port.
- Публичные фильтры больше не игнорируются без предупреждения.
- Ответы endpoint проверяются на ожидаемую структуру.

### Added

- Типизированные модели, структурированные исключения и строгая проверка входов.
- Retry/backoff, station TTL/LRU cache и lifecycle клиента.
- Bearer auth для non-loopback MCP, rate limit и healthcheck.
- Python 3.10–3.14 CI, coverage gate, type/lint/package/security checks.
- Non-root Docker image и автоматизированная публикация PyPI.

## 1.2.1 — 2026-04-01

- Последний релиз совместимого API 1.x.
