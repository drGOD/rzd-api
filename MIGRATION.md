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
