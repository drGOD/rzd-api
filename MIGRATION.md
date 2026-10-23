# Migration from 1.x to 2.0

## Python API

Используйте только `RzdClient`. Публичные `Api`, `Query`, `RzdException` и методы,
возвращавшие JSON-строки, удалены.

```python
# 1.x
from rzd_api import Api
routes_json = Api().train_routes(params)

# 2.0
from rzd_api import RzdClient
with RzdClient() as client:
    routes = client.search_tickets(origin, destination, departure_date)
    payload = [route.to_dict() for route in routes]
```

Поля результатов доступны как атрибуты моделей. Полный исходный объект РЖД
сохраняется в `.raw`.

## Configuration

- `timeout` → `connect_timeout` и `read_timeout`;
- `debug` удалён; debug-лог `rzd_api.query` настраивается стандартным Python logging;
- добавлены `base_url`, retry/backoff и параметры station cache;
- неизвестные поля и старые aliases больше не принимаются.

## Search behavior

- round-trip корректно меняет направление обратного сегмента;
- количество пассажиров задаётся через `adults` и `children`;
- `include_transfers=True` и специализированный `transport_type` возвращают
  `NotImplementedError`, поскольку современный endpoint их не поддерживает;
- некорректные и прошлые даты возвращают `RzdValidationError`.

## MCP

| 1.x | 2.0 |
|---|---|
| `train_routes` / `train_routes_return` | `search_tickets` |
| `station_code` | `find_stations` |
| `train_carriages` | `get_carriages` |
| `train_station_list` | `get_route_stations` |

SSE удалён. Для non-loopback `streamable-http` обязательно задайте
`MCP_AUTH_TOKEN` длиной не менее 32 символов.

## Migration from 2.0.0 to 3.0.0

Реальный пользовательский путь РЖД использует `CarPricing`, а не прежний
`railway/car/place/prices`. Поэтому:

- `get_carriages()` больше не принимает `car_number` и возвращает все вагоны;
- `get_route_stations()` принимает направление, дату, время и номер поезда вместо
  неподходящего `object_id`;
- добавлены методы доступности, минимальных цен, схем и изображений вагонов;
- `Config.b2b_base_url` позволяет отдельно настроить корень B2B endpoint;
- MCP публикует те же дополнительные методы.

```python
# 2.0.0
client.get_carriages(origin, destination, date, time, train, car_number="03")
client.get_route_stations(object_id)

# Актуальный контракт
cars = client.get_carriages(origin, destination, date, time, train)
route = client.get_route_stations(origin, destination, date, time, train)
```

## Migration from 3.0.0 to 3.1.0

Публичный Python `search_tickets()` сохраняет прежние типы результата, а новые
поля существующих dataclass добавлены после прежних позиционных аргументов.

### TLS

Проверка сертификата и имени сервера теперь включена. Если стандартное
хранилище CA вашей среды не доверяет цепочке РЖД, задайте доверенный PEM bundle:

```python
from rzd_api import Config, RzdClient

client = RzdClient(Config(ca_bundle="/absolute/path/ca-bundle.pem"))
```

Для Python и MCP также действует `RZD_CA_BUNDLE`. Явный `Config.ca_bundle`
имеет приоритет над этой переменной и `REQUESTS_CA_BUNDLE`. В Docker файл
нужно смонтировать и указать его путь внутри контейнера. Получение доверенного
сертификата описано в [README.md](README.md#tls-и-доверенные-сертификаты).
Автоматического перехода на соединение без проверки TLS нет.

### MCP

`raw` больше не включается в ответы tools по умолчанию. Если обработчик
использовал исходные поля РЖД, передайте `include_raw=true`. Python-модели
и их `to_dict()` продолжают сохранять полный `raw`.

У `search_tickets` новый `include_metadata=true` возвращает метаданные
направления и признак `partial`; без него сохраняется прежняя форма ответа.

### Варианты маршрута и время

`RouteStationsResult.stations` теперь содержит остановки первого варианта;
все варианты с собственными остановками доступны в `routes`. Код, которому
нужны все альтернативы, должен обходить `result.routes`, а не трактовать
их объединение как последовательность остановок одного поезда.

Старые `departure_time`/`arrival_time` у `TrainRoute` сохраняют поведение 3.0.
Для явного выбора времени используйте `local_departure_time`,
`local_arrival_time`, `moscow_departure_time`, `moscow_arrival_time`.
Подробный поиск с полнотой выдачи доступен через `search_tickets_detailed()`.
