import json

from .config import Config
from .query import Query


class Api:
    ROUTES_LAYER = 5827
    CARRIAGES_LAYER = 5764
    STATIONS_STRUCTURE_ID = 704

    def __init__(self, config: Config = None):
        if config is None:
            config = Config()

        self.lang = config.language
        self.path = f'https://pass.rzd.ru/timetable/public/{self.lang}'
        self.suggestion_path = 'https://pass.rzd.ru/suggester'
        self.station_list_path = 'https://pass.rzd.ru/ticket/services/route/basicRoute'
        self.query = Query(config)

    def train_routes(self, params: dict) -> str:
        """Получает маршруты в одну точку (one-way routes)."""
        layer = {'layer_id': self.ROUTES_LAYER}
        routes = self.query.get(self.path, {**layer, **params})
        return json.dumps(routes['tp'][0]['list'], ensure_ascii=False)

    def train_routes_return(self, params: dict) -> str:
        """Получает маршруты туда-обратно (round-trip routes)."""
        layer = {'layer_id': self.ROUTES_LAYER}
        routes = self.query.get(self.path, {**layer, **params})
        return json.dumps({
            'forward': routes['tp'][0]['list'],
            'back': routes['tp'][1]['list'],
        }, ensure_ascii=False)

    def train_carriages(self, params: dict) -> str:
        """Получение списка вагонов (carriages/cars for a specific train)."""
        layer = {'layer_id': self.CARRIAGES_LAYER}
        carriages = self.query.get(self.path, {**layer, **params})
        lst = carriages.get('lst', [{}])
        result = {
            'cars': lst[0].get('cars') if lst else None,
            'functionBlocks': lst[0].get('functionBlocks') if lst else None,
            'schemes': carriages.get('schemes'),
            'companies': carriages.get('insuranceCompany'),
        }
        return json.dumps(result, ensure_ascii=False)

    def train_station_list(self, params: dict) -> str:
        """Получение списка станций маршрута (all stations on a train's route)."""
        layer = {'STRUCTURE_ID': self.STATIONS_STRUCTURE_ID}
        stations = self.query.get(self.station_list_path, {**layer, **params})
        result = {
            'train': stations['data']['trainInfo'],
            'routes': stations['data']['routes'],
        }
        return json.dumps(result, ensure_ascii=False)

    def station_code(self, params: dict) -> str:
        """Получение кодов станций по части названия (search stations by partial name)."""
        query_params = {'lang': self.lang, **params}
        routes = self.query.get(self.suggestion_path, query_params, method='GET')

        stations = []
        station_name_part = params.get('stationNamePart', '').upper()

        if routes:
            for station in routes:
                name = station.get('n', '')
                if station_name_part in name.upper():
                    stations.append({
                        'station': name,
                        'code': station.get('c'),
                    })

        return json.dumps(stations, ensure_ascii=False)
