# RZD API — Python

Python-клиент для API сайта [pass.rzd.ru](https://pass.rzd.ru) (РЖД).  
Также включает MCP-сервер для интеграции с Claude и другими MCP-совместимыми клиентами.

## Возможности

- Маршруты в одну сторону
- Маршруты туда-обратно
- Список вагонов выбранного поезда (схема, цены, свободные места)
- Список станций по маршруту следования поезда
- Поиск кода станции по части названия

## Установка

```sh
pip install -e ".[dev]"
```

Зависимости: `requests`, `mcp`, `urllib3`.

## Быстрый старт

```python
from rzd_api import Api, Config

config = Config(
    language='ru',
    timeout=10.0,
    user_agent='Mozilla/5.0 ...',
    referer='https://ticket.rzd.ru/',
    # proxy='https://user:pass@host:port',
)

api = Api(config)  # config необязателен

# Маршруты СПб -> Москва на завтра
from datetime import datetime, timedelta
tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')

routes = api.train_routes({
    'dir': 0,           # 0 — в одну сторону
    'tfl': 3,           # 3 — поезда и электрички
    'checkSeats': 1,    # 1 — только с билетами
    'code0': '2004000', # Санкт-Петербург
    'code1': '2000000', # Москва
    'dt0': tomorrow,
    'md': 0,            # 0 — без пересадок
})
print(routes)  # JSON-строка
```

## API

### `Api(config=None)`

| Метод | Описание |
|---|---|
| `train_routes(params)` | Маршруты в одну сторону |
| `train_routes_return(params)` | Маршруты туда-обратно |
| `train_carriages(params)` | Вагоны и места |
| `train_station_list(params)` | Станции на маршруте |
| `station_code(params)` | Коды станций по части имени |

Все методы возвращают JSON-строку.

### `Config`

| Поле | По умолчанию | Описание |
|---|---|---|
| `language` | `'ru'` | Язык ответа (`'ru'`, `'en'`) |
| `timeout` | `5.0` | Таймаут запроса (сек) |
| `debug` | `False` | Режим отладки |
| `proxy` | `None` | Прокси URL |
| `user_agent` | `None` | User-Agent |
| `referer` | `None` | Referer |

## MCP-сервер

MCP-сервер позволяет использовать API РЖД прямо из Claude Desktop или любого другого MCP-клиента.

### Запуск вручную

```sh
rzd-mcp-server
# или
python -m mcp_server.server
```

### Настройка в Claude Desktop

Добавьте в `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rzd": {
      "command": "rzd-mcp-server"
    }
  }
}
```

### Доступные инструменты MCP

| Инструмент | Описание |
|---|---|
| `train_routes` | Поиск поездов в одну сторону |
| `train_routes_return` | Поиск поездов туда-обратно |
| `train_carriages` | Информация о вагонах |
| `train_station_list` | Станции на маршруте |
| `station_code` | Поиск кода станции |

## Тесты

```sh
pytest tests/
```

Тесты интеграционные — работают с живым API pass.rzd.ru.

## Как работает протокол RZD

1. Первый запрос возвращает статус `RID` (или `REQUEST_ID`) и cookie
2. Повторный запрос с тем же `rid` и cookie возвращает статус `OK` с данными
3. Библиотека автоматически управляет сессией и повторными запросами (до 10 попыток)

## Коды станций

Популярные коды:
- `2004000` — Санкт-Петербург Главный
- `2000000` — Москва (Ленинградский вокзал)

## Лицензия

MIT
