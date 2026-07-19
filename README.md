# RZD API 2.0

Типизированный Python-клиент и MCP-сервер для неофициального API
[`ticket.rzd.ru`](https://ticket.rzd.ru). Проект не связан с ОАО «РЖД»; внутренние
endpoint и схема ответов могут изменяться без предупреждения.

Поведение TLS намеренно сохранено от версии 1.x: проверка сертификата API РЖД
отключена. Не передавайте клиенту собственные секреты или учётные данные.

## Возможности

- поиск прямых поездов в одну сторону и туда-обратно;
- поиск станций по названию и синонимам;
- информация о вагонах, местах и станциях маршрута;
- dataclass-модели с полным исходным объектом в `raw`;
- MCP через `stdio` и защищённый `streamable-http`;
- retries, раздельные таймауты и кэш поиска станций.

Требуется Python 3.10–3.14.

## Установка

```sh
pip install rzd-api
```

С MCP-сервером:

```sh
pip install "rzd-api[mcp]"
```

## Python API

```python
from datetime import date, timedelta

from rzd_api import RoundTripResult, RzdClient

departure = date.today() + timedelta(days=14)
return_date = departure + timedelta(days=3)

with RzdClient() as client:
    result = client.search_tickets(
        "Москва",
        "Санкт-Петербург",
        departure,
        return_date=return_date,
        adults=1,
        children=0,
    )

    if isinstance(result, RoundTripResult):
        for train in result.forward:
            print(train.number, train.departure_time, train.min_price)
        for train in result.back:
            print(train.number, train.departure_time, train.min_price)
```

Все модели поддерживают `to_dict()` и содержат необработанный узел ответа в `raw`.

### Методы `RzdClient`

| Метод | Результат |
|---|---|
| `search_tickets(...)` | `list[TrainRoute]` или `RoundTripResult` |
| `find_stations(query, ...)` | `list[Station]` |
| `resolve_station_code(station)` | код станции |
| `get_carriages(...)` | `CarriageResult` |
| `get_route_stations(object_id)` | `RouteStationsResult` |

`only_with_seats=True` фильтрует по доступности мест из `CarGroups`. Современный
pricing endpoint не поддерживает маршруты с пересадками и фильтр типа транспорта,
поэтому `include_transfers=True` и `transport_type="trains"|"suburban"` явно
возвращают `NotImplementedError`.

### Конфигурация

```python
from rzd_api import Config, RzdClient

config = Config(
    language="ru",
    connect_timeout=5,
    read_timeout=20,
    retry_total=3,
    retry_backoff=0.5,
    station_cache_ttl=3600,
    station_cache_size=256,
    proxy=None,
)
client = RzdClient(config)
```

Ошибки наследуются от `RzdError`: validation, transport, HTTP, API, schema,
station-not-found и ambiguous-station.

## MCP

Инструменты: `search_tickets`, `find_stations`, `get_carriages`,
`get_route_stations`.

Локальный stdio:

```sh
rzd-mcp-server
```

Streamable HTTP на loopback без токена:

```sh
MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 rzd-mcp-server
```

При привязке к non-loopback адресу требуется Bearer-токен минимум из 32 символов:

```sh
export MCP_AUTH_TOKEN="replace-with-a-random-token-at-least-32-characters"
MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 rzd-mcp-server
```

Endpoint MCP: `http://localhost:8000/mcp`; healthcheck: `/health`. Лимит по
умолчанию — 60 запросов в минуту, настраивается через
`MCP_RATE_LIMIT_PER_MINUTE`. Допустимые Host headers можно перечислить через
`MCP_ALLOWED_HOSTS`.

## Docker

```sh
export MCP_AUTH_TOKEN="replace-with-a-random-token-at-least-32-characters"
docker compose up -d
curl http://127.0.0.1:8000/health
```

Контейнер запускается от UID 10001, без Linux capabilities, и публикует порт
только на loopback хоста.

## Разработка

```sh
python -m pip install -e ".[dev]"
make check
```

Live smoke test является opt-in:

```sh
RZD_LIVE_TEST=1 pytest tests/integration -m integration -v
```

Переход с 1.x описан в [MIGRATION.md](MIGRATION.md), изменения релизов — в
[CHANGELOG.md](CHANGELOG.md).

## Лицензия

MIT
