# RZD API — Python

Python-клиент для API сайта [ticket.rzd.ru](https://ticket.rzd.ru) (РЖД).  
Включает MCP-сервер для интеграции с Claude и другими MCP-совместимыми клиентами.

## Возможности

- Маршруты в одну сторону
- Маршруты туда-обратно
- Список вагонов (схема, цены, свободные места)
- Список станций по маршруту следования поезда
- Поиск кода станции по части названия

---

## Установка

**Из PyPI после публикации:**
```sh
pip install rzd-api
```

**Как библиотека без MCP-зависимостей:**
```sh
pip install rzd-api
```

**С поддержкой MCP-сервера:**
```sh
pip install "rzd-api[mcp]"
```

**Напрямую из GitHub:**
```sh
pip install "git+https://github.com/drGOD/rzd-api.git"
```

**Напрямую из GitHub c MCP-сервером:**
```sh
pip install "rzd-api[mcp] @ git+https://github.com/drGOD/rzd-api.git"
```

**Из исходников:**
```sh
pip install .
```

**Из исходников c MCP-сервером:**
```sh
pip install ".[mcp]"
```

**Для разработки (с тестами):**
```sh
pip install -e ".[dev]"
# или
make install
```

**Проверка импорта после установки:**
```sh
python -c "from rzd_api import RzdClient; print(RzdClient.__name__)"
```

**Проверка MCP-команды после установки extra:**
```sh
rzd-mcp-server
```

---

## Быстрый старт

### Как библиотека

```python
from datetime import date
from rzd_api import RzdClient

client = RzdClient()

# Можно передавать названия станций, клиент сам найдёт их коды
tickets = client.search_tickets(
    from_station='Санкт-Петербург',
    to_station='Москва',
    departure_date=date(2026, 4, 1),
)

for train in tickets[:3]:
    print(
        train.get('TrainNumber') or train.get('DisplayTrainNumber'),
        train.get('OriginStationName'),
        train.get('DestinationStationName'),
        train.get('DepartureDateTime') or train.get('LocalDepartureDateTime'),
        train.get('ArrivalDateTime') or train.get('LocalArrivalDateTime'),
    )

# Туда-обратно
round_trip = client.search_tickets(
    from_station='Санкт-Петербург',
    to_station='Москва',
    departure_date='01.04.2026',
    return_date='05.04.2026',
)
print('Туда:', len(round_trip['forward']), 'Обратно:', len(round_trip['back']))

# Поиск станций и получение кода
stations = client.find_stations('Чеб')
code = client.resolve_station_code('Москва')

# Детали по вагонам
if tickets:
    first_train = tickets[0]
    dep_time = (first_train.get('DepartureDateTime') or first_train.get('LocalDepartureDateTime'))[11:16]
    train_no = first_train.get('TrainNumber') or first_train.get('DisplayTrainNumber')

    try:
        cars = client.get_carriages(
            from_station='Санкт-Петербург',
            to_station='Москва',
            departure_date='01.04.2026',
            departure_time=dep_time,
            train_number=train_no,
            car_number='01',  # для этого endpoint нужен конкретный номер вагона
        )
        print(cars.get('cars'))
    except Exception as exc:
        print('Не удалось получить вагоны/места:', exc)
```

### Низкоуровневый API

```python
from datetime import datetime, timedelta
from rzd_api import Api, Config

config = Config(
    language='ru',       # язык ответа: 'ru' или 'en'
    timeout=10.0,        # таймаут запроса в секундах
    user_agent='Mozilla/5.0 ...',
    referer='https://ticket.rzd.ru/',
    # proxy='https://user:pass@host:port',
    # debug=True,        # включить HTTP-лог
)

api = Api(config)   # config необязателен

tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')

# Маршруты Санкт-Петербург → Москва
routes = api.train_routes({
    'origin': '2004000',      # код станции отправления
    'destination': '2000000', # код станции прибытия
    'departureDate': tomorrow,
    'adultPassengersQuantity': 1,
    'childrenPassengersQuantity': 0,
})
print(routes)   # JSON-строка
```

---

## API

### `RzdClient(config=None, api=None)`

Высокоуровневый интерфейс для использования пакета как библиотеки.  
Методы возвращают обычные Python-объекты (`list` / `dict`) и принимают станции как коды или названия.

| Метод | Описание |
|---|---|
| `search_tickets(from_station, to_station, departure_date, return_date=None, *, only_with_seats=True, include_transfers=False, transport_type='all')` | Удобный поиск билетов |
| `find_stations(query, transport_type='rail,suburban', group_results=True)` | Поиск станций по части названия |
| `resolve_station_code(station)` | Получить код станции по названию или вернуть переданный код |
| `get_carriages(from_station, to_station, departure_date, departure_time, train_number, *, car_number='01', provider='P1')` | Вагоны и свободные места |
| `get_route_stations(object_id)` | Список станций маршрута |

#### `search_tickets`

| Параметр | Описание |
|---|---|
| `from_station` / `to_station` | Код станции (`2004000`) или название (`Санкт-Петербург`) |
| `departure_date` / `return_date` | `str`, `datetime.date` или `datetime.datetime` |
| `only_with_seats` | `True` — только поезда с билетами |
| `include_transfers` | `True` — искать варианты с пересадками |
| `transport_type` | `'trains'`, `'suburban'`, `'all'` |

### `Api(config=None)`

Низкоуровневый совместимый интерфейс. Методы ниже сохраняют текущее поведение и возвращают **JSON-строку**.  
Если нужен Python-объект без `json.loads`, можно использовать парные методы с суффиксом `_data`.

| Метод | Описание |
|---|---|
| `train_routes(params)` | Маршруты в одну сторону |
| `train_routes_data(params)` | Маршруты в одну сторону как `list[dict]` |
| `train_routes_return(params)` | Маршруты туда-обратно |
| `train_routes_return_data(params)` | Маршруты туда-обратно как `dict` |
| `train_carriages(params)` | Вагоны и свободные места |
| `train_carriages_data(params)` | Вагоны и свободные места как `dict` |
| `train_station_list(params)` | Все станции на маршруте поезда |
| `train_station_list_data(params)` | Все станции на маршруте как `dict` |
| `station_code(params)` | Поиск кода станции по части названия |
| `station_code_data(params)` | Поиск кода станции как `list[dict]` |

#### `train_routes` / `train_routes_return`

| Параметр | Описание |
|---|---|
| `origin` | Код станции отправления |
| `destination` | Код станции прибытия |
| `departureDate` | Дата/время отправления в ISO, например `2026-04-13T00:00:00` |
| `returnDate` | Дата/время возврата в ISO (только для `train_routes_return`) |
| `adultPassengersQuantity` | Количество взрослых пассажиров |
| `childrenPassengersQuantity` | Количество детей |
| `service_provider` | Провайдер, обычно `B2B_RZD` |

#### `train_carriages`

| Параметр | Описание |
|---|---|
| `OriginCode` / `DestinationCode` | Коды станций |
| `DepartureDate` | Дата/время отправления в ISO |
| `TrainNumber` | Номер поезда (например `054Г`) |
| `CarNumber` | Номер вагона |
| `Provider` | Код провайдера, обычно `P1` |

#### `train_station_list`

| Параметр | Описание |
|---|---|
| `id` | Идентификатор объекта для endpoint `/getobject` |

#### `station_code`

| Параметр | Описание |
|---|---|
| `stationNamePart` | Часть названия станции (мин. 2 символа, например `ЧЕБ`) |
| `transportType` | Типы транспорта, по умолчанию `rail,suburban` |
| `groupResults` | Группировка результатов, по умолчанию `true` |

### `Config`

| Поле | По умолчанию | Описание |
|---|---|---|
| `language` | `'ru'` | Язык ответа (`'ru'`, `'en'`) |
| `timeout` | `5.0` | Таймаут запроса (сек) |
| `debug` | `False` | HTTP-лог в stderr (уровень DEBUG) |
| `proxy` | `None` | URL прокси |
| `user_agent` | `None` | User-Agent |
| `referer` | `None` | Referer |

---

## MCP-сервер

MCP-сервер позволяет использовать API РЖД напрямую из Claude Desktop или любого MCP-клиента.

Для локального запуска нужен extra `mcp`:
```sh
pip install "rzd-api[mcp]"
```

### Инструменты

| Инструмент | Описание |
|---|---|
| `train_routes` | Поиск поездов в одну сторону |
| `train_routes_return` | Поиск поездов туда-обратно |
| `train_carriages` | Информация о вагонах |
| `train_station_list` | Станции на маршруте |
| `station_code` | Поиск кода станции |

### Запуск локально (stdio)

```sh
rzd-mcp-server
# или
make run
```

**Настройка в Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rzd": {
      "command": "rzd-mcp-server"
    }
  }
}
```

### Запуск через Docker (HTTP)

```sh
docker compose up -d
# или
make docker-up
```

Сервер запустится на `http://localhost:8000` (транспорт `streamable-http`).

**Настройка в Claude Desktop** для удалённого сервера:

```json
{
  "mcpServers": {
    "rzd": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Переменные окружения MCP-сервера

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | Транспорт: `stdio`, `sse`, `streamable-http` |
| `MCP_HOST` | `0.0.0.0` | Хост для HTTP-транспортов |
| `MCP_PORT` | `8000` | Порт для HTTP-транспортов |

---

## Docker

```sh
# Сборка образа
docker build -t rzd-api .

# Запуск
docker run -p 8000:8000 rzd-api

# С кастомным портом
docker run -p 9000:9000 -e MCP_PORT=9000 rzd-api
```

---

## Тесты

```sh
pytest tests/ -v
# или
make test
```

Тесты unit-style и не требуют доступа к живому API.

---

## Как работает протокол RZD

Библиотека использует `ticket.rzd.ru/api/v1` и работает с современным JSON-форматом ответа.
При ошибках API поднимается `RzdException` с кодом и сообщением из `errorInfo`.

## Популярные коды станций

| Станция | Код |
|---|---|
| Санкт-Петербург Главный | `2004000` |
| Москва (Ленинградский вокзал) | `2000000` |
| Москва (Казанский вокзал) | `2000001` |
| Новосибирск Главный | `2060600` |
| Екатеринбург Пасс. | `2030000` |

Для поиска кода любой станции используйте метод `station_code`.

## Лицензия

MIT
