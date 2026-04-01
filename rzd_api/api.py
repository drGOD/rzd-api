from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from .config import Config
from .query import Query


class Api:
    def __init__(self, config: Config = None):
        if config is None:
            config = Config()

        self.lang = config.language
        self.base_path = 'https://ticket.rzd.ru/api/v1'
        self.query = Query(config)

    def train_routes_data(self, params: dict) -> list[dict]:
        """Получает маршруты в одну точку как Python-объект."""
        request_params = self._build_train_pricing_params(params)
        payload = self.query.get(
            f'{self.base_path}/railway-service/prices/train-pricing',
            request_params,
            method='GET',
        )
        return self._extract_list(payload)

    def train_routes(self, params: dict) -> str:
        """Получает маршруты в одну точку (one-way routes)."""
        return json.dumps(self.train_routes_data(params), ensure_ascii=False)

    def train_routes_return_data(self, params: dict) -> dict[str, list[dict]]:
        """Получает маршруты туда-обратно как Python-объект."""
        forward_params = dict(params)
        back_params = dict(params)
        back_params['dt0'] = params['dt1']

        return {
            'forward': self.train_routes_data(forward_params),
            'back': self.train_routes_data(back_params),
        }

    def train_routes_return(self, params: dict) -> str:
        """Получает маршруты туда-обратно (round-trip routes)."""
        return json.dumps(self.train_routes_return_data(params), ensure_ascii=False)

    def train_carriages_data(self, params: dict) -> dict:
        """Получение списка вагонов как Python-объект."""
        query_params = {'service_provider': params.get('service_provider', 'B2B_RZD')}
        body = self._build_car_place_prices_body(params)
        payload = self.query.get(
            f'{self.base_path}/railway/car/place/prices',
            query_params,
            method='POST',
            json_body=body,
        )

        cars = self._extract_cars(payload)
        return {
            'cars': cars,
            'functionBlocks': payload.get('functionBlocks') if isinstance(payload, dict) else None,
            'schemes': payload.get('schemes') if isinstance(payload, dict) else None,
            'companies': payload.get('insuranceCompany') if isinstance(payload, dict) else None,
            'raw': payload,
        }

    def train_carriages(self, params: dict) -> str:
        """Получение списка вагонов (carriages/cars for a specific train)."""
        return json.dumps(self.train_carriages_data(params), ensure_ascii=False)

    def train_station_list_data(self, params: dict) -> dict:
        """Получение списка станций маршрута как Python-объект."""
        query_params = {
            'id': params.get('objectId') or params.get('id') or params.get('trainNumber'),
        }
        payload = self.query.get(f'{self.base_path}/getobject', query_params, method='GET')
        if isinstance(payload, dict):
            return {
                'train': payload.get('train') or payload.get('trainInfo') or {},
                'routes': payload.get('routes') or payload.get('stations') or [],
                'raw': payload,
            }
        return {'train': {}, 'routes': [], 'raw': payload}

    def train_station_list(self, params: dict) -> str:
        """Получение списка станций маршрута (all stations on a train's route)."""
        return json.dumps(self.train_station_list_data(params), ensure_ascii=False)

    def station_code_data(self, params: dict) -> list[dict]:
        """Получение кодов станций по части названия как Python-объект."""
        query = str(params.get('stationNamePart', '')).strip()
        request_params = {
            'Query': query,
            'TransportType': params.get('transportType', 'rail,suburban'),
            'GroupResults': str(params.get('groupResults', True)).lower(),
            'RailwaySortPriority': str(params.get('railwaySortPriority', True)).lower(),
            'SynonymOn': int(bool(params.get('synonymOn', 1))),
            'Language': self.lang,
        }
        payload = self.query.get(f'{self.base_path}/suggests', request_params, method='GET')

        stations: list[dict[str, str]] = []
        for node in self._iter_dict_nodes(payload):
            code = self._first_non_empty(
                node,
                ['ExpressCode', 'expressCode', 'code', 'Code', 'c'],
            )
            name = self._first_non_empty(
                node,
                ['NameRu', 'nameRu', 'name', 'Name', 'n', 'title'],
            )
            if not code or not name:
                continue

            station_name = str(name)
            if query and query.upper() not in station_name.upper():
                continue

            stations.append({
                'station': station_name,
                'code': str(code),
            })

        unique: dict[tuple[str, str], dict[str, str]] = {}
        for item in stations:
            unique[(item['station'], item['code'])] = item
        return list(unique.values())

    def station_code(self, params: dict) -> str:
        """Получение кодов станций по части названия (search stations by partial name)."""
        return json.dumps(self.station_code_data(params), ensure_ascii=False)

    def _build_train_pricing_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            'service_provider': params.get('service_provider', 'B2B_RZD'),
            'getByLocalTime': self._bool_param(params.get('getByLocalTime', True)),
            'carGrouping': params.get('carGrouping', 'DontGroup'),
            'origin': params.get('origin', params.get('code0')),
            'destination': params.get('destination', params.get('code1')),
            'departureDate': params.get(
                'departureDate',
                self._to_iso_datetime(params.get('dt0')),
            ),
            'specialPlacesDemand': params.get(
                'specialPlacesDemand',
                'StandardPlacesAndForDisabledPersons',
            ),
            'carIssuingType': params.get('carIssuingType', 'Passenger'),
            'getTrainsFromSchedule': self._bool_param(params.get('getTrainsFromSchedule', True)),
            'adultPassengersQuantity': params.get(
                'adultPassengersQuantity',
                params.get('adults', 1),
            ),
            'childrenPassengersQuantity': params.get(
                'childrenPassengersQuantity',
                params.get('children', 0),
            ),
            'hasPlacesForLargeFamily': self._bool_param(
                params.get('hasPlacesForLargeFamily', False),
            ),
        }

    def _build_car_place_prices_body(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            'OriginCode': params.get('OriginCode', params.get('code0')),
            'DestinationCode': params.get('DestinationCode', params.get('code1')),
            'Provider': params.get('Provider', 'P1'),
            'DepartureDate': params.get(
                'DepartureDate',
                self._to_iso_datetime(params.get('dt0'), params.get('time0')),
            ),
            'TrainNumber': params.get('TrainNumber', params.get('tnum0')),
            'SpecialPlacesDemand': params.get(
                'SpecialPlacesDemand',
                'StandardPlacesAndForDisabledPersons',
            ),
            'TariffType': params.get('TariffType', 'Single'),
            'CarNumber': params.get('CarNumber', params.get('carNumber', '01')),
        }

    def _extract_cars(self, payload: dict | list) -> list[dict] | None:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return None

        for key in ('cars', 'Cars', 'carriages', 'Carriages', 'places', 'Places', 'Data'):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = self._extract_cars(value)
                if nested is not None:
                    return nested

        for value in payload.values():
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = self._extract_cars(value)
                if nested is not None:
                    return nested
        return None

    def _extract_list(self, payload: dict | list) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        for key in ('list', 'items', 'data', 'result', 'routes', 'trains', 'Trains'):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = self._extract_list(value)
                if nested:
                    return nested

        for value in payload.values():
            if isinstance(value, dict):
                nested = self._extract_list(value)
                if nested:
                    return nested
            if isinstance(value, list):
                return value
        return []

    def _to_iso_datetime(self, value: Any, time_value: str | None = None) -> str | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M:%S')
        if isinstance(value, date):
            return value.strftime('%Y-%m-%dT00:00:00')

        raw = str(value).strip()
        if not raw:
            return None
        if 'T' in raw:
            return raw

        try:
            parsed = datetime.strptime(raw, '%d.%m.%Y')
            if time_value:
                t = datetime.strptime(time_value, '%H:%M').time()
                parsed = datetime.combine(parsed.date(), t)
            return parsed.strftime('%Y-%m-%dT%H:%M:%S')
        except ValueError:
            return raw

    def _bool_param(self, value: Any) -> str:
        if isinstance(value, str):
            return value.lower()
        return 'true' if bool(value) else 'false'

    def _iter_dict_nodes(self, payload: Any):
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from self._iter_dict_nodes(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_dict_nodes(item)

    def _first_non_empty(self, source: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            value = source.get(key)
            if value not in (None, ''):
                return value
        return None
