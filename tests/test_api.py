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


def test_find_stations_parses_current_category_response() -> None:
    api, _ = make_api(
        {
            "city": [
                {
                    "nodeId": "city-id",
                    "expressCode": "2000000",
                    "name": "Москва",
                    "nodeType": "city",
                    "transportType": "city",
                    "region": "Российская Федерация",
                }
            ],
            "train": [
                {
                    "nodeId": "station-id",
                    "expressCode": "2000002",
                    "name": "Москва Ярославская",
                    "nodeType": "station",
                    "transportType": "train",
                    "region": "Москва, Российская Федерация",
                }
            ],
        }
    )
    stations = api.find_stations(query="Москва", transport_type="rail", group_results=True)
    assert [item.code for item in stations] == ["2000000", "2000002"]
    assert stations[0].node_id == "city-id"
    assert stations[1].transport_type == "train"


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

    api, _ = make_api({"city": {}})
    with pytest.raises(RzdSchemaError, match="must be a list"):
        api.find_stations(query="Нет", transport_type="rail", group_results=True)


def test_train_availability_parses_current_contract() -> None:
    api, transport = make_api(
        {
            "OriginCode": "2000000",
            "DestinationCode": "2004000",
            "AvailabilityItems": [{"Date": "2099-04-03T00:00:00"}],
        }
    )
    result = api.get_train_availability(
        origin="2000000", destination="2004000", date_from="2099-04-01", date_to="2099-04-30"
    )
    assert result.items[0].date == "2099-04-03T00:00:00"
    assert transport.calls[0]["params"]["originStationCode"] == "2000000"


def test_minimal_pricing_parses_current_contract_and_api_typo() -> None:
    api, _ = make_api(
        {
            "OriginStationCode": "2000000",
            "DestinationStationCode": "2004000",
            "PriceByDepartureDates": [
                {
                    "DepatureDate": "2099-04-03T00:00:00",
                    "MinPrice": 2597.2,
                    "DisabledPlaceMinPrice": 4263,
                    "Carriers": [{"CarrierName": "ФПК"}],
                }
            ],
        }
    )
    result = api.get_minimal_pricing(
        origin="2000000", destination="2004000", date_from="2099-04-03"
    )
    assert result.prices[0].date == "2099-04-03T00:00:00"
    assert result.prices[0].min_price == 2597.2
    assert result.prices[0].carriers[0]["CarrierName"] == "ФПК"


def test_carriages_use_current_car_pricing_contract() -> None:
    api, transport = make_api(
        {
            "OriginCode": "1",
            "DestinationCode": "2",
            "Cars": [
                {
                    "CarNumber": "03",
                    "CarType": "Compartment",
                    "CarSubType": "01К",
                    "CarTypeName": "Купе",
                    "ServiceClass": "2Э",
                    "RailwayCarSchemeId": 334,
                    "CarSchemeName": "01К",
                    "Carrier": "ФПК",
                    "CarDirection": "NoValue",
                    "CarNumeration": "FromHead",
                    "TrainNumber": "001А",
                    "MinPrice": "4500.25",
                    "MaxPrice": 5200,
                    "ServiceCost": 100,
                    "PlaceQuantity": 7,
                    "FreePlaces": "1, 2, 3",
                    "Services": ["Bedclothes"],
                    "HasImages": True,
                }
            ],
            "TrainInfo": {
                "TrainNumber": "001А",
                "DepartureDateTime": "2099-01-01T10:00:00",
            },
            "RoutePolicy": "Internal",
            "BookingSystem": "Express3",
            "AllowedDocumentTypes": ["RussianPassport"],
            "OriginRetrievalDate": "2098-12-01T00:00:00",
        }
    )
    result = api.get_carriages(
        origin="1",
        destination="2",
        departure_date="2099-01-01T10:00:00",
        train_number="001А",
        provider="P1",
    )
    assert result.cars[0].number == "03"
    assert result.cars[0].available_places == 7
    assert result.cars[0].scheme_id == 334
    assert result.cars[0].service_class == "2Э"
    assert result.cars[0].services == ["Bedclothes"]
    assert result.train_number == "001А"
    call = transport.calls[0]
    assert call["url"].endswith("/Railway/V1/Search/CarPricing")
    assert call["json_body"]["TrainNumber"] == "001А"
    assert "CarNumber" not in call["json_body"]
    assert "TariffType" not in call["json_body"]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"Cars": [1]},
        {"Cars": [], "TrainInfo": {}, "AllowedDocumentTypes": {}},
        {"Cars": [{"Services": {}}], "TrainInfo": {}, "AllowedDocumentTypes": []},
    ],
)
def test_carriages_reject_invalid_schema(payload: Any) -> None:
    api, _ = make_api(payload)
    with pytest.raises(RzdSchemaError):
        api.get_carriages(
            origin="1",
            destination="2",
            departure_date="2099-01-01T10:00:00",
            train_number="1",
            provider="P1",
        )


def test_car_scheme_and_images_parse_current_contracts() -> None:
    api, transport = make_api(
        {
            "SchemeId": 334,
            "CarSubType": "01Л",
            "PcSchemeFirstStorey": "/334/PcFirstStorey",
            "Direction": "Unknown",
        },
        {
            "SchemeId": 334,
            "CarSubType": "01Л",
            "Images": [
                {
                    "RailwayCarImageId": 757,
                    "TitleRu": "Интерьер купе",
                    "Preview": "/757/Preview",
                    "Content": "/757/Content",
                    "SequenceNumber": 1,
                }
            ],
        },
    )
    params = {
        "car_sub_type": "01Л",
        "car_number": "06",
        "service_class": "1Э",
        "carrier": "ФПК",
        "train_number": "059Г",
        "departure_date": "2099-01-01T10:00:00",
        "car_numeration": "FromHead",
    }
    scheme = api.get_car_scheme(**params)
    images = api.get_car_images(**params)
    assert scheme.first_storey == "/334/PcFirstStorey"
    assert images.images[0].image_id == 757
    assert transport.calls[0]["url"].endswith("/railway-service/carscheme")
    assert transport.calls[1]["url"].endswith("/railway-service/carimage/list")


def test_route_stations_use_current_train_route_contract() -> None:
    api, transport = make_api(
        {
            "Routes": [
                {
                    "Name": "Россия",
                    "OriginName": "МОСКВА",
                    "DestinationName": "С-ПЕТЕРБУРГ",
                    "TrainNumber": "054Г",
                    "RouteStops": [
                        {
                            "StationName": "МОСКВА",
                            "CityName": "Москва",
                            "StationCode": "2000000",
                            "DepartureDateTime": "2099-01-01T10:00:00",
                            "StopDuration": 5,
                            "DaysFromFormingStation": 0,
                            "ActualMovement": True,
                        }
                    ],
                }
            ]
        }
    )
    result = api.get_route_stations(
        origin="1",
        destination="2",
        departure_date="2099-01-01T10:00:00",
        train_number="054Г",
        provider="P1",
    )
    assert result.train_number == "054Г"
    assert result.stations[0].name == "МОСКВА"
    assert result.stations[0].city_name == "Москва"
    assert result.stations[0].actual_movement is True
    assert transport.calls[0]["url"].endswith("/Railway/V1/Search/TrainRoute")
    assert transport.calls[0]["params"]["GetNewRoute"] == "true"


@pytest.mark.parametrize("payload", [[], {}, {"Routes": {}}, {"Routes": [1]}, {"Routes": []}])
def test_route_stations_reject_invalid_schema(payload: Any) -> None:
    api, _ = make_api(payload)
    with pytest.raises(RzdSchemaError):
        api.get_route_stations(
            origin="1",
            destination="2",
            departure_date="2099-01-01T10:00:00",
            train_number="054Г",
            provider="P1",
        )


def test_api_close_delegates_to_transport() -> None:
    api, transport = make_api()
    api.close()
    assert transport.closed is True
