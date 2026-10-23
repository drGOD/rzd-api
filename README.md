# RZD API

Типизированный Python-клиент и MCP-сервер для неофициального API
[`ticket.rzd.ru`](https://ticket.rzd.ru). Проект не связан с ОАО «РЖД»; внутренние
endpoint и схема ответов могут изменяться без предупреждения.

Проверка TLS-сертификата и имени сервера включена. Для своей доверенной цепочки
используйте `Config(ca_bundle="/path/to/ca-bundle.pem")` или `RZD_CA_BUNDLE`.

## Возможности

- поиск прямых поездов в одну сторону и туда-обратно;
- поиск станций по названию и синонимам;
- календарь доступности и минимальные цены по датам;
- информация о вагонах, местах, схемах, изображениях и станциях маршрута;
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

Все модели поддерживают `to_dict()`. Исходные узлы ответов сохраняются в `raw`;
у составного `RoundTripSearchResult` они находятся в `forward.raw` и `back.raw`.

### Методы `RzdClient`

| Метод | Результат |
|---|---|
| `search_tickets(...)` | `list[TrainRoute]` или `RoundTripResult` |
| `search_tickets_detailed(...)` | `TrainSearchResult` или `RoundTripSearchResult` |
| `find_stations(query, ...)` | `list[Station]` |
| `resolve_station_code(station)` | код станции |
| `get_carriages(...)` | `CarriageResult` |
| `get_train_availability(...)` | `TrainAvailabilityResult` |
| `get_minimal_prices(...)` | `MinimalPricingResult` |
| `get_car_scheme(...)` | `CarScheme` |
| `get_car_images(...)` | `CarImagesResult` |
| `get_route_stations(...)` | `RouteStationsResult` |

`get_carriages()` использует актуальный `CarPricing` и сразу возвращает все вагоны
поезда. `car_number` этому методу больше не передаётся. Значения `number`,
`car_sub_type`, `service_class`, `carrier` и `numeration` из выбранного `Carriage`
можно передать в `get_car_scheme()` и `get_car_images()`.

```python
with RzdClient() as client:
    carriages = client.get_carriages(
        "2001025", "2004001", departure, "00:48", "059Г"
    )
    car = carriages.cars[0]
    scheme = client.get_car_scheme(
        departure,
        "00:48",
        car.train_number or "059Г",
        car.number or "",
        car.car_sub_type or "",
        car.service_class or "",
        car.carrier or "",
        car_numeration=car.numeration or "FromHead",
    )
```

`only_with_seats=True` фильтрует по доступности мест из `CarGroups`. Современный
pricing endpoint не поддерживает маршруты с пересадками и фильтр типа транспорта,
поэтому `include_transfers=True` и `transport_type="trains"|"suburban"` явно
возвращают `NotImplementedError`.

`search_tickets_detailed()` принимает те же параметры, но сохраняет метаданные
направления: `trains`, `partial` (`NotAllTrainsReturned`), `moscow_time` и `raw`.
`partial=None` означает, что источник не сообщил о полноте. Для туда-обратно
`forward` и `back` содержат отдельные `TrainSearchResult`. Фильтрация мест не
меняет исходный `raw` и не превращает неполный ответ в полный.

У `TrainRoute` явно разделены `local_departure_time`/`local_arrival_time` и
`moscow_departure_time`/`moscow_arrival_time`. Старые `departure_time` и
`arrival_time` сохраняют приоритет московского времени из версии 3.0;
для показа местного времени используйте новые поля.

`get_route_stations()` возвращает все варианты в `routes: list[RouteVariant]`.
Старые `stations`, `train_number` и названия относятся к **первому** варианту:
остановки разных маршрутов больше не склеиваются. Необязательный
`actual_movement` допускает boolean, 0/1 и строки `true`/`false`; неизвестное
значение становится `None` и сохраняется в `raw`. Остальные ошибки схемы
продолжают вызывать `RzdSchemaError`.

Поиск станций поддерживает категории `city`/`train`, а также ISDK-формат
`transport_node_suggests` с `Codes.Railway`, `CityId`, `Timezone` и `Stations`.
Узлы разных вокзалов с одинаковым кодом сохраняются отдельно. Узлы без
железнодорожного кода не подставляются в поиск поездов. По умолчанию используется
прежний `/api/v1/suggests`; для ISDK задайте
`Config(station_search_url="https://ticket.rzd.ru/isdk/suggests")`.

### Конфигурация

```python
from rzd_api import Config, RzdClient

config = Config(
    language="ru",
    # По умолчанию выводится из base_url.
    b2b_base_url=None,
    connect_timeout=5,
    read_timeout=20,
    retry_total=3,
    retry_backoff=0.5,
    station_cache_ttl=3600,
    station_cache_size=256,
    proxy=None,
    ca_bundle=None,  # Или RZD_CA_BUNDLE; проверка TLS всегда включена.
    station_search_url=None,
)
client = RzdClient(config)
```

Ошибки наследуются от `RzdError`: validation, transport, HTTP, API, schema,
station-not-found и ambiguous-station.

### TLS и доверенные сертификаты

При `CERTIFICATE_VERIFY_FAILED` настройте доверенную цепочку для своей среды.
Корневой сертификат российского НУЦ следует получать с
[официальной страницы Госуслуг](https://www.gosuslugi.ru/crt), проверяя источник
и отпечаток. Библиотека не скачивает сертификаты и не меняет системное хранилище.
`ca_bundle` — путь к PEM bundle с необходимыми доверенными CA; явно заданный
путь имеет приоритет над `RZD_CA_BUNDLE` и `REQUESTS_CA_BUNDLE`.
Без него используются стандартные настройки доверия Requests.

Для MCP переменная `RZD_CA_BUNDLE` действует на все tools. В Docker смонтируйте
файл только для чтения и передайте путь **внутри контейнера**:

```sh
docker run --rm -i \
  --mount type=bind,src=/absolute/path/ca-bundle.pem,dst=/run/rzd-ca.pem,readonly \
  -e RZD_CA_BUNDLE=/run/rzd-ca.pem \
  -e MCP_TRANSPORT=stdio rzd-api:3.0.0
```

TLS/HTTP/transport errors остаются исключениями, а не пустым результатом поиска.

## MCP

Инструменты: `search_tickets`, `find_stations`, `get_carriages`,
`get_train_availability`, `get_minimal_prices`, `get_car_scheme`,
`get_car_images`, `get_route_stations`.

Все tools по умолчанию исключают `raw` на всех уровнях ответа. Передайте
`include_raw=true`, если нужны исходные поля РЖД. Python-модели и их `to_dict()`
сохраняют полный `raw`. Списки не обрезаются молча.

У `search_tickets` флаг `include_metadata=true` возвращает подробный результат
с `partial` и серверным временем; без него сохраняется прежняя форма списка
или пары направлений. Для оценки полноты выдачи используйте этот флаг.

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

Для живого API нужен сетевой выход с доступом к РЖД и настроенный CA bundle.
Live-тесты не повторяют запросы автоматически. `RZD_LIVE_PROXY` задаёт proxy
только для этих тестов. Еженедельный GitHub live smoke включается переменной
репозитория `RZD_LIVE_ENABLED=true` после настройки доступа; без неё расписание
пропускается. `RZD_LIVE_RUNNER` позволяет выбрать подходящий runner, секрет
`RZD_LIVE_PROXY` — proxy. Ручной запуск доступен независимо от расписания.
Workflow получает CA с официального HTTPS-источника и проверяет закреплённый
SHA-256 отпечаток; при ротации сертификата проверка завершится ошибкой.
Offline CI запускается независимо от наличия сетевого доступа к РЖД.

Переход с 1.x описан в [MIGRATION.md](MIGRATION.md), изменения релизов — в
[CHANGELOG.md](CHANGELOG.md).

## Лицензия

MIT

Происхождение заимствований и благодарности авторам — в [CREDITS.md](CREDITS.md).
