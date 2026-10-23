from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from test_api import make_api
from test_client import FakeApi, future_date, route

from rzd_api import (
    RoundTripSearchResult,
    RzdClient,
    RzdSchemaError,
    Station,
    TrainSearchResult,
)


def suggestion(**updates: Any) -> dict[str, Any]:
    return {
        "Name": "Чебоксары",
        "NodeId": "city-node",
        "CityId": "city-node",
        "Codes": {"Railway": "2060620", "Cbdpr": "5389", "Avia": "CSY"},
        "Timezone": "Europe/Moscow",
        "CountryISO": "RU",
        "SubType": "Город",
        "Stations": [{"Codes": {"Railway": "2060620"}}, {"Codes": {"Railway": "2060206"}}],
        **updates,
    }


def test_isdk_station_contract_preserves_nodes_codes_and_timezone() -> None:
    city = suggestion()
    station = suggestion(NodeId="station-node", SubType="Станция")
    api, transport = make_api({"transport_node_suggests": [city, city, station]})
    api.config.station_search_url = "https://example.test/isdk/suggests"
    result = api.find_stations(query="Чебоксары", transport_type="rail", group_results=True)
    assert [item.node_id for item in result] == ["city-node", "station-node"]
    assert result[0].city_id == "city-node"
    assert result[0].timezone == "Europe/Moscow"
    assert result[0].codes["Avia"] == "CSY"
    assert result[0].station_codes == ["2060620", "2060206"]
    assert result[0].country == "RU"
    assert result[0].raw == city
    assert transport.calls[0]["url"] == "https://example.test/isdk/suggests"


def test_non_railway_nodes_are_not_used_as_railway_codes() -> None:
    api, _ = make_api({"transport_node_suggests": [suggestion(Codes={"Bus": "bus-node"})]})
    assert api.find_stations(query="Чебоксары", transport_type="rail", group_results=True) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"transport_node_suggests": None},
        {"transport_node_suggests": [suggestion(Codes=[])]},
        {"transport_node_suggests": [suggestion(Codes={"Railway": {}})]},
        {"transport_node_suggests": [suggestion(Codes={"Cbdpr": True})]},
        {"transport_node_suggests": [suggestion(Stations={})]},
        {"transport_node_suggests": [suggestion(Stations=[{"Codes": []}])]},
        {"city": [{"name": "X", "expressCode": {}}]},
    ],
)
def test_malformed_station_response_is_not_an_empty_result(payload: Any) -> None:
    api, _ = make_api(payload)
    with pytest.raises(RzdSchemaError):
        api.find_stations(query="Чебоксары", transport_type="rail", group_results=True)


def test_station_additions_keep_old_positional_arguments() -> None:
    item = Station("Москва", "1", {}, "node", "city", "rail", "region")
    assert (item.node_type, item.transport_type, item.region) == ("city", "rail", "region")
    assert item.codes == {}


def test_station_deduplication_preserves_distinct_suburban_codes() -> None:
    api, _ = make_api(
        {
            "transport_node_suggests": [
                suggestion(Codes={"Railway": "1", "Cbdpr": "2"}),
                suggestion(Codes={"Railway": "1", "Cbdpr": "3"}),
            ]
        }
    )
    result = api.find_stations(query="Город", transport_type="rail,suburban", group_results=True)
    assert len(result) == 2


def test_search_preserves_partial_even_with_no_trains() -> None:
    payload = {
        "Trains": [],
        "NotAllTrainsReturned": True,
        "MoscowDateTime": "2099-01-01T12:00:00",
        "OriginCode": "1",
        "DestinationCode": "2",
    }
    api, _ = make_api(payload)
    result = api.get_train_search_result(
        origin="1", destination="2", departure_date="2099-01-02", adults=1, children=0
    )
    assert result.trains == []
    assert result.partial is True
    assert result.moscow_time == "2099-01-01T12:00:00"
    assert result.raw == payload


def test_local_and_moscow_departure_can_have_different_dates() -> None:
    api, _ = make_api(
        {
            "Trains": [
                {
                    "TrainNumber": "1",
                    "DepartureDateTime": "2099-01-01T22:00:00",
                    "LocalDepartureDateTime": "2099-01-02T03:00:00",
                }
            ]
        }
    )
    result = api.get_train_routes(
        origin="1", destination="2", departure_date="2099-01-02", adults=1, children=0
    )[0]
    assert result.local_departure_time == "2099-01-02T03:00:00"
    assert result.moscow_departure_time == "2099-01-01T22:00:00"
    assert result.departure_time == result.moscow_departure_time  # Preserve the 3.0 field.


def test_detailed_client_preserves_metadata_and_round_trip_direction() -> None:
    class MetadataApi(FakeApi):
        def get_train_search_result(self, **kwargs: Any) -> TrainSearchResult:
            return TrainSearchResult(
                trains=self.get_train_routes(**kwargs),
                partial=True,
                raw={"NotAllTrainsReturned": True},
            )

    api = MetadataApi()
    api.routes = [route("empty", places=0), route("available")]
    with RzdClient(_api=api) as client:  # type: ignore[arg-type]
        result = client.search_tickets_detailed("1", "2", future_date(), future_date(35))
    assert isinstance(result, RoundTripSearchResult)
    assert result.forward.partial is True
    assert result.back.partial is True
    assert [train.number for train in result.forward.trains] == ["available"]
    assert api.calls[-1][1]["origin"] == "2"


def test_route_variants_are_not_concatenated() -> None:
    routes = [
        {"Name": "Main", "TrainNumber": "1", "RouteStops": [{"StationName": "Москва"}]},
        {"Name": "Attached", "TrainNumber": "2", "RouteStops": [{"StationName": "Казань"}]},
    ]
    source = deepcopy(routes)
    api, _ = make_api({"Routes": routes})
    result = api.get_route_stations(
        origin="1", destination="2", departure_date="2099-01-02", train_number="1", provider="P1"
    )
    assert [station.name for station in result.stations] == ["Москва"]
    assert [variant.route_name for variant in result.routes] == ["Main", "Attached"]
    assert result.routes[1].stations[0].name == "Казань"
    assert result.routes[1].raw == source[1]
    assert result.raw == {"Routes": source}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (0, False),
        (1, True),
        (" TRUE ", True),
        ("false", False),
        ("", None),
        (None, None),
        ({"unknown": True}, None),
    ],
)
def test_actual_movement_does_not_discard_route(value: Any, expected: bool | None) -> None:
    api, _ = make_api(
        {"Routes": [{"RouteStops": [{"StationName": "Москва", "ActualMovement": value}]}]}
    )
    result = api.get_route_stations(
        origin="1", destination="2", departure_date="2099-01-02", train_number="1", provider="P1"
    )
    assert result.stations[0].actual_movement is expected


@pytest.mark.parametrize(
    "stop", [{}, {"Error": "no route"}, {"StationName": "X", "IsCutawayStation": "junk"}]
)
def test_other_route_schema_errors_remain_strict(stop: dict[str, Any]) -> None:
    api, _ = make_api({"Routes": [{"RouteStops": [stop]}]})
    with pytest.raises(RzdSchemaError):
        api.get_route_stations(
            origin="1",
            destination="2",
            departure_date="2099-01-02",
            train_number="1",
            provider="P1",
        )


def test_explicit_null_minimal_pricing_is_empty_but_missing_keys_are_errors() -> None:
    api, _ = make_api(
        {"OriginStationCode": None, "DestinationStationCode": None, "PriceByDepartureDates": None},
        {"OriginStationCode": "1", "DestinationStationCode": "2"},
    )
    result = api.get_minimal_pricing(origin="1", destination="2", date_from="2099-01-02")
    assert (result.origin_code, result.destination_code, result.prices) == ("1", "2", [])
    with pytest.raises(RzdSchemaError):
        api.get_minimal_pricing(origin="1", destination="2", date_from="2099-01-02")
