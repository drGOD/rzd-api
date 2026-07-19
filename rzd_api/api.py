from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .config import Config
from .exceptions import RzdSchemaError
from .models import (
    CarGroup,
    Carriage,
    CarriageResult,
    JsonObject,
    RouteStation,
    RouteStationsResult,
    Station,
    TrainRoute,
)
from .query import JsonPayload, RzdTransport


class RzdApi:
    """Internal endpoint adapter for ticket.rzd.ru API v1."""

    def __init__(self, config: Config, transport: RzdTransport | None = None) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.transport = transport or RzdTransport(config)

    def get_train_routes(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int,
        children: int,
    ) -> list[TrainRoute]:
        payload = self.transport.request_json(
            "GET",
            f"{self.base_url}/railway-service/prices/train-pricing",
            params={
                "service_provider": "B2B_RZD",
                "getByLocalTime": "true",
                "carGrouping": "DontGroup",
                "origin": origin,
                "destination": destination,
                "departureDate": departure_date,
                "specialPlacesDemand": "StandardPlacesAndForDisabledPersons",
                "carIssuingType": "Passenger",
                "getTrainsFromSchedule": "true",
                "adultPassengersQuantity": adults,
                "childrenPassengersQuantity": children,
                "hasPlacesForLargeFamily": "false",
            },
        )
        nodes = self._train_nodes(payload)
        return [self._parse_train(node) for node in nodes]

    def find_stations(
        self,
        *,
        query: str,
        transport_type: str,
        group_results: bool,
    ) -> list[Station]:
        payload = self.transport.request_json(
            "GET",
            f"{self.base_url}/suggests",
            params={
                "Query": query,
                "TransportType": transport_type,
                "GroupResults": str(group_results).lower(),
                "RailwaySortPriority": "true",
                "SynonymOn": 1,
                "Language": self.config.language,
            },
        )
        nodes = self._suggestion_nodes(payload)
        if not self._station_nodes_match_schema(nodes):
            raise RzdSchemaError(
                "The station suggestion response contains unsupported station nodes."
            )
        stations = list(self._parse_station_nodes(nodes))
        unique: dict[tuple[str, str], Station] = {}
        for station in stations:
            unique[(station.name, station.code)] = station
        return list(unique.values())

    def get_carriages(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: str,
        train_number: str,
        car_number: str,
        provider: str,
    ) -> CarriageResult:
        payload = self.transport.request_json(
            "POST",
            f"{self.base_url}/railway/car/place/prices",
            params={"service_provider": "B2B_RZD"},
            json_body={
                "OriginCode": origin,
                "DestinationCode": destination,
                "Provider": provider,
                "DepartureDate": departure_date,
                "TrainNumber": train_number,
                "SpecialPlacesDemand": "StandardPlacesAndForDisabledPersons",
                "TariffType": "Single",
                "CarNumber": car_number,
            },
        )
        root = self._object_payload(payload, "carriage")
        car_nodes = self._car_nodes(root)
        return CarriageResult(
            cars=[self._parse_carriage(node) for node in car_nodes],
            function_blocks=root.get("functionBlocks"),
            schemes=root.get("schemes"),
            companies=root.get("insuranceCompany"),
            raw=root,
        )

    def get_route_stations(self, *, object_id: str) -> RouteStationsResult:
        payload = self.transport.request_json(
            "GET",
            f"{self.base_url}/getobject",
            params={"id": object_id},
        )
        root = self._object_payload(payload, "route stations")
        data = root.get("data") if isinstance(root.get("data"), dict) else root
        assert isinstance(data, dict)

        train = data.get("train") or data.get("trainInfo") or {}
        if not isinstance(train, dict):
            raise RzdSchemaError("The route-stations 'train' field must be an object.")
        route_nodes = data.get("routes") if "routes" in data else data.get("stations")
        if not isinstance(route_nodes, list):
            raise RzdSchemaError("The route-stations response has no supported routes list.")
        if not all(isinstance(node, dict) for node in route_nodes):
            raise RzdSchemaError("Every route-stations item must be an object.")

        return RouteStationsResult(
            train_number=self._string(train, "TrainNumber", "trainNumber", "number"),
            stations=[self._parse_route_station(node) for node in route_nodes],
            raw=root,
        )

    @staticmethod
    def _train_nodes(payload: JsonPayload) -> list[JsonObject]:
        value: Any = payload
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), dict):
                value = payload["data"]
            if isinstance(value, dict):
                value = value.get("Trains") if "Trains" in value else value.get("trains")
        if not isinstance(value, list):
            raise RzdSchemaError("The train-pricing response has no supported trains list.")
        if not all(isinstance(node, dict) for node in value):
            raise RzdSchemaError("Every train-pricing item must be an object.")
        return value

    @classmethod
    def _parse_train(cls, node: JsonObject) -> TrainRoute:
        number = cls._string(node, "TrainNumber", "trainNumber")
        display_number = cls._string(node, "DisplayTrainNumber", "displayTrainNumber")
        if not number and not display_number:
            raise RzdSchemaError("A train item does not contain a train number.")

        group_nodes = node.get("CarGroups") if "CarGroups" in node else node.get("carGroups")
        if group_nodes is None and "CarGroups" not in node and "carGroups" not in node:
            groups: list[CarGroup] = []
            available_places = None
        else:
            if group_nodes is None:
                raise RzdSchemaError("A train item contains an invalid CarGroups field.")
            if not isinstance(group_nodes, list) or not all(
                isinstance(group, dict) for group in group_nodes
            ):
                raise RzdSchemaError("A train item contains an invalid CarGroups field.")
            groups = [cls._parse_car_group(group) for group in group_nodes]
            available_places = cls._aggregate_places(groups)
        min_price = cls._number(node, "MinPrice", "minPrice")
        if min_price is None:
            prices = [group.min_price for group in groups if group.min_price is not None]
            min_price = min(prices) if prices else None

        return TrainRoute(
            number=number or display_number or "",
            display_number=display_number,
            origin_name=cls._string(node, "OriginStationName", "originStationName"),
            destination_name=cls._string(node, "DestinationStationName", "destinationStationName"),
            departure_time=cls._string(
                node,
                "DepartureDateTime",
                "departureDateTime",
                "LocalDepartureDateTime",
                "localDepartureDateTime",
            ),
            arrival_time=cls._string(
                node,
                "ArrivalDateTime",
                "arrivalDateTime",
                "LocalArrivalDateTime",
                "localArrivalDateTime",
            ),
            min_price=min_price,
            available_places=available_places,
            car_groups=groups,
            raw=node,
        )

    @classmethod
    def _parse_car_group(cls, node: JsonObject) -> CarGroup:
        return CarGroup(
            car_type=cls._string(node, "CarType", "carType", "Type", "type"),
            min_price=cls._number(node, "MinPrice", "minPrice", "Price", "price"),
            available_places=cls._available_places(node),
            raw=node,
        )

    @classmethod
    def _parse_carriage(cls, node: JsonObject) -> Carriage:
        return Carriage(
            number=cls._string(node, "CarNumber", "carNumber", "Number", "number"),
            car_type=cls._string(node, "CarType", "carType", "Type", "type"),
            min_price=cls._number(node, "MinPrice", "minPrice", "Price", "price"),
            available_places=cls._available_places(node),
            raw=node,
        )

    @classmethod
    def _parse_route_station(cls, node: JsonObject) -> RouteStation:
        return RouteStation(
            name=cls._string(node, "StationName", "stationName", "Name", "name"),
            code=cls._string(node, "StationCode", "stationCode", "Code", "code"),
            arrival_time=cls._string(
                node, "ArrivalDateTime", "arrivalDateTime", "ArrivalTime", "arrivalTime"
            ),
            departure_time=cls._string(
                node,
                "DepartureDateTime",
                "departureDateTime",
                "DepartureTime",
                "departureTime",
            ),
            distance=cls._integer(node, "Distance", "distance"),
            raw=node,
        )

    @classmethod
    def _suggestion_nodes(cls, payload: JsonPayload) -> list[Any]:
        if isinstance(payload, list):
            return payload
        for key in ("suggestions", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        if not payload:
            return []
        raise RzdSchemaError("The station suggestion response has no supported items list.")

    @classmethod
    def _parse_station_nodes(cls, nodes: Iterable[Any]) -> Iterable[Station]:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            code = cls._string(node, "ExpressCode", "expressCode", "code", "Code", "c")
            name = cls._string(node, "NameRu", "nameRu", "name", "Name", "n", "title")
            if code and name:
                yield Station(name=name, code=code, raw=node)
                continue
            for key in ("stations", "items", "children", "Children"):
                nested = node.get(key)
                if isinstance(nested, list):
                    yield from cls._parse_station_nodes(nested)

    @classmethod
    def _station_nodes_match_schema(cls, nodes: Iterable[Any]) -> bool:
        for node in nodes:
            if not isinstance(node, dict):
                return False
            code = cls._string(node, "ExpressCode", "expressCode", "code", "Code", "c")
            name = cls._string(node, "NameRu", "nameRu", "name", "Name", "n", "title")
            if code and name:
                continue

            nested_values = [
                node[key] for key in ("stations", "items", "children", "Children") if key in node
            ]
            if not nested_values:
                return False
            for nested in nested_values:
                if not isinstance(nested, list) or not cls._station_nodes_match_schema(nested):
                    return False
        return True

    @staticmethod
    def _car_nodes(root: JsonObject) -> list[JsonObject]:
        candidates: list[Any] = [root.get("cars"), root.get("Cars")]
        for data_key in ("data", "Data"):
            data = root.get(data_key)
            if isinstance(data, dict):
                candidates.extend([data.get("cars"), data.get("Cars")])
        value = next((candidate for candidate in candidates if candidate is not None), None)
        if not isinstance(value, list):
            raise RzdSchemaError("The carriage response has no supported cars list.")
        if not all(isinstance(node, dict) for node in value):
            raise RzdSchemaError("Every carriage item must be an object.")
        return value

    @staticmethod
    def _object_payload(payload: JsonPayload, endpoint: str) -> JsonObject:
        if not isinstance(payload, dict):
            raise RzdSchemaError(f"The {endpoint} response must be an object.")
        return payload

    @classmethod
    def _available_places(cls, node: JsonObject) -> int | None:
        for key in (
            "TotalPlaceQuantity",
            "totalPlaceQuantity",
            "PlaceQuantity",
            "placeQuantity",
            "FreePlaces",
            "freePlaces",
        ):
            value = cls._coerce_int(node.get(key))
            if value is not None:
                return value

        category_values = [
            cls._coerce_int(node.get(key))
            for key in (
                "LowerPlaceQuantity",
                "lowerPlaceQuantity",
                "UpperPlaceQuantity",
                "upperPlaceQuantity",
                "SideLowerPlaceQuantity",
                "sideLowerPlaceQuantity",
                "SideUpperPlaceQuantity",
                "sideUpperPlaceQuantity",
            )
            if key in node
        ]
        if category_values and all(value is not None for value in category_values):
            return sum(value for value in category_values if value is not None)
        return None

    @staticmethod
    def _aggregate_places(groups: list[CarGroup]) -> int | None:
        if not groups:
            return 0
        values = [group.available_places for group in groups]
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    @staticmethod
    def _string(node: JsonObject, *keys: str) -> str | None:
        for key in keys:
            value = node.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    @classmethod
    def _number(cls, node: JsonObject, *keys: str) -> float | None:
        for key in keys:
            value = node.get(key)
            if value in (None, "") or isinstance(value, bool):
                continue
            try:
                return float(str(value))
            except (TypeError, ValueError):
                raise RzdSchemaError(f"Field {key} must be numeric.") from None
        return None

    @classmethod
    def _integer(cls, node: JsonObject, *keys: str) -> int | None:
        for key in keys:
            if key in node:
                value = cls._coerce_int(node.get(key))
                if value is None and node.get(key) not in (None, ""):
                    raise RzdSchemaError(f"Field {key} must be an integer.")
                return value
        return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def close(self) -> None:
        self.transport.close()
