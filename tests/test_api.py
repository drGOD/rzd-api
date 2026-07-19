from __future__ import annotations

from typing import Any

import pytest

from rzd_api.api import RzdApi
from rzd_api.config import Config
from rzd_api.exceptions import RzdSchemaError


class FakeTransport:
    def __init__(self, payloads: list[Any]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.payloads.pop(0)

    def close(self) -> None:
        self.closed = True


def make_api(*payloads: Any) -> tuple[RzdApi, FakeTransport]:
    transport = FakeTransport(list(payloads))
    return RzdApi(Config(), transport=transport), transport  # type: ignore[arg-type]


def test_train_routes_builds_current_request_and_parses_models() -> None:
    api, transport = make_api(
        {
            "data": {
                "trains": [
                    {
                        "TrainNumber": "001А",
                        "DisplayTrainNumber": "001А",
                        "OriginStationName": "МОСКВА",
                        "DestinationStationName": "С-ПЕТЕРБУРГ",
                        "DepartureDateTime": "2099-04-03T22:30:00",
                        "ArrivalDateTime": "2099-04-04T06:30:00",
                        "CarGroups": [
                            {
                                "CarType": "Compartment",
                                "MinPrice": 4200.5,
                                "TotalPlaceQuantity": 4,
                            },
                            {
                                "CarType": "ReservedSeat",
                                "MinPrice": "2500",
                                "LowerPlaceQuantity": 2,
                                "UpperPlaceQuantity": 3,
                            },
                        ],
                    }
                ]
            }
        }
    )

    routes = api.get_train_routes(
        origin="2000000",
        destination="2004000",
        departure_date="2099-04-03T00:00:00",
        adults=2,
        children=1,
    )

    assert routes[0].number == "001А"
    assert routes[0].available_places == 9
    assert routes[0].min_price == 2500.0
    assert routes[0].car_groups[0].car_type == "Compartment"
    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"].endswith("/railway-service/prices/train-pricing")
    assert call["params"]["adultPassengersQuantity"] == 2
    assert call["params"]["childrenPassengersQuantity"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {}},
        {"Trains": ["not-an-object"]},
        {"Trains": [{"OriginStationName": "missing number"}]},
        {"Trains": [{"TrainNumber": "1", "CarGroups": {}}]},
    ],
)
def test_train_routes_rejects_schema_drift(payload: Any) -> None:
    api, _ = make_api(payload)
    with pytest.raises(RzdSchemaError):
        api.get_train_routes(
            origin="1", destination="2", departure_date="2099-01-01T00:00:00", adults=1, children=0
        )


def test_train_route_marks_missing_car_groups_as_unknown_availability() -> None:
    api, _ = make_api({"Trains": [{"TrainNumber": "001А"}]})
    route = api.get_train_routes(
        origin="1", destination="2", departure_date="2099-01-01T00:00:00", adults=1, children=0
    )[0]
    assert route.available_places is None
    assert route.car_groups == []


def test_train_route_marks_unknown_availability() -> None:
    api, _ = make_api({"Trains": [{"TrainNumber": "001А", "CarGroups": [{"CarType": "Unknown"}]}]})
    route = api.get_train_routes(
        origin="1", destination="2", departure_date="2099-01-01T00:00:00", adults=1, children=0
    )[0]
    assert route.available_places is None


def test_find_stations_preserves_synonyms_and_grouped_nodes() -> None:
    api, _ = make_api(
        [
            {"group": "rail", "items": [{"n": "САНКТ-ПЕТЕРБУРГ", "c": "2004000"}]},
            {"n": "САНКТ-ПЕТЕРБУРГ", "c": "2004000"},
        ]
    )
    stations = api.find_stations(query="Питер", transport_type="rail", group_results=True)
    assert [(item.name, item.code) for item in stations] == [("САНКТ-ПЕТЕРБУРГ", "2004000")]


def test_find_stations_accepts_empty_and_rejects_unknown_nonempty_schema() -> None:
    api, _ = make_api([])
    assert api.find_stations(query="Нет", transport_type="rail", group_results=True) == []

    api, _ = make_api({"suggestions": []})
    assert api.find_stations(query="Нет", transport_type="rail", group_results=True) == []

    api, _ = make_api([{"group": "rail", "items": []}])
    assert api.find_stations(query="Нет", transport_type="rail", group_results=True) == []

    api, _ = make_api([{"unknown": "value"}])
    with pytest.raises(RzdSchemaError, match="unsupported station"):
        api.find_stations(query="Нет", transport_type="rail", group_results=True)


def test_carriages_are_parsed_from_explicit_data_path() -> None:
    api, transport = make_api(
        {
            "data": {
                "cars": [
                    {
                        "CarNumber": "03",
                        "CarType": "Compartment",
                        "MinPrice": "4500.25",
                        "TotalPlaceQuantity": 7,
                    }
                ]
            },
            "functionBlocks": ["x"],
            "schemes": {"a": 1},
            "insuranceCompany": ["company"],
        }
    )
    result = api.get_carriages(
        origin="1",
        destination="2",
        departure_date="2099-01-01T10:00:00",
        train_number="001А",
        car_number="03",
        provider="P1",
    )
    assert result.cars[0].number == "03"
    assert result.cars[0].available_places == 7
    assert result.function_blocks == ["x"]
    assert transport.calls[0]["json_body"]["TrainNumber"] == "001А"


@pytest.mark.parametrize("payload", [[], {}, {"cars": [1]}])
def test_carriages_reject_invalid_schema(payload: Any) -> None:
    api, _ = make_api(payload)
    with pytest.raises(RzdSchemaError):
        api.get_carriages(
            origin="1",
            destination="2",
            departure_date="2099-01-01T10:00:00",
            train_number="1",
            car_number="1",
            provider="P1",
        )


def test_route_stations_supports_data_wrapper() -> None:
    api, _ = make_api(
        {
            "data": {
                "trainInfo": {"TrainNumber": "054Г"},
                "routes": [
                    {
                        "StationName": "МОСКВА",
                        "StationCode": "2000000",
                        "DepartureTime": "10:00",
                        "Distance": "0",
                    }
                ],
            }
        }
    )
    result = api.get_route_stations(object_id="object-1")
    assert result.train_number == "054Г"
    assert result.stations[0].name == "МОСКВА"
    assert result.stations[0].distance == 0


@pytest.mark.parametrize("payload", [[], {}, {"routes": {}}, {"routes": [1]}])
def test_route_stations_reject_invalid_schema(payload: Any) -> None:
    api, _ = make_api(payload)
    with pytest.raises(RzdSchemaError):
        api.get_route_stations(object_id="object-1")


def test_api_close_delegates_to_transport() -> None:
    api, transport = make_api()
    api.close()
    assert transport.closed is True
