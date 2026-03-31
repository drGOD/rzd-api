# RZD API — Python

Python-клиент для API сайта [pass.rzd.ru](https://pass.rzd.ru) (РЖД).  
Включает MCP-сервер для интеграции с Claude и другими MCP-совместимыми клиентами.

## Возможности

- Маршруты в одну сторону
- Маршруты туда-обратно
- Список вагонов (схема, цены, свободные места)
- Список станций по маршруту следования поезда
- Поиск кода станции по части названия

---

## Установка

**Из исходников:**
```sh
pip install .
```

**Для разработки (с тестами):**
```sh
pip install -e ".[dev]"
# или
make install
```

---

## Быстрый старт

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

### `Api(config=None)`

Все методы принимают `dict` с параметрами и возвращают **JSON-строку**.

| Метод | Описание |
|---|---|
| `train_routes(params)` | Маршруты в одну сторону |
| `train_routes_return(params)` | Маршруты туда-обратно |
| `train_carriages(params)` | Вагоны и свободные места |
| `train_station_list(params)` | Все станции на маршруте поезда |
| `station_code(params)` | Поиск кода станции по части названия |

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

Тесты интеграционные — работают с живым API pass.rzd.ru.

---

## Как работает протокол RZD

1. Первый запрос возвращает статус `RID` / `REQUEST_ID` + cookie
2. Повторный запрос с тем же `rid` и cookie возвращает статус `OK` с данными
3. Библиотека управляет сессией и повторными запросами автоматически (до 10 попыток, интервал 1 сек)

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
