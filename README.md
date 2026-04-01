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
    print(train['number'], train['route0'], train['route1'], train['time0'], train['time1'])

# Туда-обратно
round_trip = client.search_tickets(
    from_station='Санкт-Петербург',
    to_station='Москва',
    departure_date='01.04.2026',
    return_date='05.04.2026',
)

# Поиск станций и получение кода
stations = client.find_stations('Чеб')
code = client.resolve_station_code('Москва')

# Детали по вагонам
cars = client.get_carriages(
    from_station='Санкт-Петербург',
    to_station='Москва',
    departure_date='01.04.2026',
    departure_time='22:30',
    train_number='054А',
)
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

tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')

# Маршруты Санкт-Петербург → Москва
routes = api.train_routes({
    'dir':        0,          # 0 — в одну сторону
    'tfl':        3,          # 3 — поезда и электрички, 1 — только поезда, 2 — только электрички
    'checkSeats': 1,          # 1 — только с билетами, 0 — все поезда
    'code0':      '2004000',  # код станции отправления
    'code1':      '2000000',  # код станции прибытия
    'dt0':        tomorrow,   # дата отправления dd.mm.yyyy
    'md':         0,          # 0 — без пересадок, 1 — с пересадками
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
| `find_stations(query, compact_mode='y')` | Поиск станций по части названия |
| `resolve_station_code(station)` | Получить код станции по названию или вернуть переданный код |
| `get_carriages(from_station, to_station, departure_date, departure_time, train_number)` | Вагоны и свободные места |
| `get_route_stations(train_number, departure_date)` | Список станций маршрута |

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
| `code0` | Код станции отправления |
| `code1` | Код станции прибытия |
| `dt0` | Дата отправления `dd.mm.yyyy` |
| `dt1` | Дата возврата `dd.mm.yyyy` (только для `train_routes_return`) |
| `dir` | `0` — в одну сторону, `1` — туда-обратно |
| `tfl` | `1` — поезда, `2` — электрички, `3` — всё |
| `checkSeats` | `1` — только с билетами, `0` — все |
| `md` | `0` — без пересадок, `1` — с пересадками |

#### `train_carriages`

| Параметр | Описание |
|---|---|
| `code0` / `code1` | Коды станций |
| `dt0` | Дата отправления `dd.mm.yyyy` |
| `time0` | Время отправления `HH:MM` |
| `tnum0` | Номер поезда (например `054Г`) |

#### `train_station_list`

| Параметр | Описание |
|---|---|
| `trainNumber` | Номер поезда (например `054Г`) |
| `depDate` | Дата отправления `dd.mm.yyyy` |

#### `station_code`

| Параметр | Описание |
|---|---|
| `stationNamePart` | Часть названия станции (мин. 2 символа, например `ЧЕБ`) |
| `compactMode` | Формат ответа, по умолчанию `y` |

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
