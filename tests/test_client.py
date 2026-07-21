from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from rzd_api import (
    CarImagesResult,
    CarriageResult,
    CarScheme,
    Config,
    MinimalPricingResult,
    RoundTripResult,
    RouteStationsResult,
    RzdAmbiguousStationError,
    RzdClient,
    RzdSchemaError,
    RzdStationNotFoundError,
    RzdValidationError,
    Station,
    TrainAvailabilityResult,
    TrainRoute,
)


def future_date(days: int = 30) -> date:
    return date.today() + timedelta(days=days)


def route(
    number: str = "001A",
    *,
    places: int | None = 4,
    departure: str = "2099-04-03T22:30:00",
) -> TrainRoute:
    return TrainRoute(
        number=number,
        display_number=number,
        origin_name="МОСКВА",
        destination_name="С-ПЕТЕРБУРГ",
        departure_time=departure,
        arrival_time="2099-04-04T06:00:00",
        min_price=1000.0,
        available_places=places,
        car_groups=[],
        raw={"TrainNumber": number},
    )


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.routes: list[TrainRoute] = [route()]
        self.stations: list[Station] = [
            Station("МОСКВА", "2000000", {}),
            Station("САНКТ-ПЕТЕРБУРГ", "2004000", {}),
        ]
        self.closed = False

    def get_train_routes(self, **kwargs: Any) -> list[TrainRoute]:
        self.calls.append(("get_train_routes", kwargs))
        return list(self.routes)

    def find_stations(self, **kwargs: Any) -> list[Station]:
        self.calls.append(("find_stations", kwargs))
        folded = kwargs["query"].casefold()
        return [item for item in self.stations if folded in item.name.casefold()] or list(
            self.stations
        )

    def get_carriages(self, **kwargs: Any) -> CarriageResult:
        self.calls.append(("get_carriages", kwargs))
        return CarriageResult(raw={})

    def get_train_availability(self, **kwargs: Any) -> TrainAvailabilityResult:
        self.calls.append(("get_train_availability", kwargs))
        return TrainAvailabilityResult("1", "2", raw={})

    def get_minimal_pricing(self, **kwargs: Any) -> MinimalPricingResult:
        self.calls.append(("get_minimal_pricing", kwargs))
        return MinimalPricingResult("1", "2", raw={})

    def get_car_scheme(self, **kwargs: Any) -> CarScheme:
        self.calls.append(("get_car_scheme", kwargs))
        return CarScheme(
            None, None, None, None, None, None, None, None, None, None, None, None, None
        )

    def get_car_images(self, **kwargs: Any) -> CarImagesResult:
        self.calls.append(("get_car_images", kwargs))
        return CarImagesResult(None, None, raw={})

    def get_route_stations(self, **kwargs: Any) -> RouteStationsResult:
        self.calls.append(("get_route_stations", kwargs))
        return RouteStationsResult(train_number="001A", raw={})

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def client(api: FakeApi) -> RzdClient:
    return RzdClient(Config(), _api=api)  # type: ignore[arg-type]


def test_round_trip_swaps_direction_and_returns_models(client: RzdClient, api: FakeApi) -> None:
    result = client.search_tickets(
        "2000000",
        "2004000",
        future_date(30),
        return_date=future_date(35),
        adults=2,
        children=1,
    )
    assert isinstance(result, RoundTripResult)
    assert result.forward[0].number == "001A"
    forward = api.calls[0][1]
    back = api.calls[1][1]
    assert (forward["origin"], forward["destination"]) == ("2000000", "2004000")
    assert (back["origin"], back["destination"]) == ("2004000", "2000000")
    assert forward["adults"] == 2
    assert forward["children"] == 1


def test_only_with_seats_filters_and_detects_unknown_schema(
    client: RzdClient, api: FakeApi
) -> None:
    api.routes = [route("1", places=0), route("2", places=3)]
    result = client.search_tickets("1", "2", future_date())
    assert isinstance(result, list)
    assert [item.number for item in result] == ["2"]

    api.routes = [route("3", places=None)]
    with pytest.raises(RzdSchemaError, match="Cannot determine"):
        client.search_tickets("1", "2", future_date())
    result = client.search_tickets("1", "2", future_date(), only_with_seats=False)
    assert isinstance(result, list)
    assert result[0].number == "3"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"include_transfers": True}, NotImplementedError),
        ({"transport_type": "trains"}, NotImplementedError),
        ({"transport_type": "plane"}, RzdValidationError),
        ({"adults": 0}, RzdValidationError),
        ({"adults": True}, RzdValidationError),
        ({"children": -1}, RzdValidationError),
        ({"children": False}, RzdValidationError),
    ],
)
def test_search_rejects_unsupported_or_invalid_options(
    client: RzdClient, kwargs: dict[str, Any], error: type[Exception]
) -> None:
    with pytest.raises(error):
        client.search_tickets("1", "2", future_date(), **kwargs)


@pytest.mark.parametrize(
    "value",
    [
        "31.12.2099",
        "2099-12-31",
        "2099-12-31T12:34:56",
        "2099-12-31T09:34:56Z",
        date(2099, 12, 31),
        datetime(2099, 12, 31, 12, 34),
    ],
)
def test_supported_date_formats(client: RzdClient, api: FakeApi, value: Any) -> None:
    client.search_tickets("1", "2", value, only_with_seats=False)
    assert api.calls[-1][1]["departure_date"].startswith("2099-12-31T")


def test_invalid_past_and_return_dates(client: RzdClient, api: FakeApi) -> None:
    with pytest.raises(RzdValidationError, match="past"):
        client.search_tickets("1", "2", "2020-01-01")
    with pytest.raises(RzdValidationError, match="format"):
        client.search_tickets("1", "2", "tomorrow")
    with pytest.raises(RzdValidationError, match="earlier"):
        client.search_tickets("1", "2", future_date(20), return_date=future_date(10))
    assert api.calls == []


def test_search_rejects_same_station(client: RzdClient) -> None:
    with pytest.raises(RzdValidationError, match="different"):
        client.search_tickets("1", "1", future_date())


def test_station_cache_and_resolution(client: RzdClient, api: FakeApi) -> None:
    first = client.find_stations("Москва")
    second = client.find_stations("москва")
    assert first == second
    assert [call[0] for call in api.calls].count("find_stations") == 1
    assert client.resolve_station_code("Москва") == "2000000"
    assert client.resolve_station_code(2004000) == "2004000"


def test_station_cache_eviction_and_disabled_cache(api: FakeApi) -> None:
    client = RzdClient(Config(station_cache_size=1), _api=api)  # type: ignore[arg-type]
    client.find_stations("Москва")
    client.find_stations("Петербург")
    client.find_stations("Москва")
    assert [call[0] for call in api.calls].count("find_stations") == 3

    api.calls.clear()
    client = RzdClient(Config(station_cache_ttl=0), _api=api)  # type: ignore[arg-type]
    client.find_stations("Москва")
    client.find_stations("Москва")
    assert [call[0] for call in api.calls].count("find_stations") == 2


def test_station_cache_ttl_expiry(api: FakeApi, monkeypatch: pytest.MonkeyPatch) -> None:
    timestamps = iter((100.0, 101.0, 111.0))
    monkeypatch.setattr("rzd_api.client.time.monotonic", lambda: next(timestamps))
    client = RzdClient(Config(station_cache_ttl=10), _api=api)  # type: ignore[arg-type]
    client.find_stations("Москва")
    client.find_stations("Москва")
    client.find_stations("Москва")
    assert [call[0] for call in api.calls].count("find_stations") == 2


def test_station_errors_and_validation(client: RzdClient, api: FakeApi) -> None:
    with pytest.raises(RzdValidationError):
        client.find_stations("M")
    with pytest.raises(RzdValidationError):
        client.find_stations("Москва", transport_type=" ")
    with pytest.raises(RzdValidationError):
        client.resolve_station_code("")

    api.stations = []
    with pytest.raises(RzdStationNotFoundError):
        client.resolve_station_code("Неизвестная")

    api.stations = [Station("МОСКВА-1", "1", {}), Station("МОСКВА-2", "2", {})]
    with pytest.raises(RzdAmbiguousStationError) as exc_info:
        client.resolve_station_code("Москва")
    assert len(exc_info.value.candidates) == 2


def test_exact_station_with_duplicate_code_is_not_ambiguous(
    client: RzdClient, api: FakeApi
) -> None:
    api.stations = [Station("МОСКВА", "1", {}), Station("МОСКВА", "1", {"duplicate": True})]
    assert client.resolve_station_code("Москва") == "1"


def test_get_carriages_validates_train_and_calls_endpoint(client: RzdClient, api: FakeApi) -> None:
    target = future_date(30)
    result = client.get_carriages("1", "2", target, "22:30", "001A")
    assert isinstance(result, CarriageResult)
    assert api.calls[-1][0] == "get_carriages"
    assert api.calls[-1][1]["departure_date"].endswith("T22:30:00")


def test_get_carriages_rejects_invalid_inputs(client: RzdClient, api: FakeApi) -> None:
    target = future_date()
    with pytest.raises(RzdValidationError, match="HH:MM"):
        client.get_carriages("1", "2", target, "25:00", "001A")
    with pytest.raises(RzdValidationError, match="must not be empty"):
        client.get_carriages("1", "2", target, "22:30", "")
    with pytest.raises(RzdValidationError, match="different"):
        client.get_carriages("1", "1", target, "22:30", "001A")


def test_availability_and_minimal_prices_validate_dates(client: RzdClient, api: FakeApi) -> None:
    start = future_date(10)
    end = future_date(20)
    client.get_train_availability("1", "2", start, end)
    assert api.calls[-1] == (
        "get_train_availability",
        {
            "origin": "1",
            "destination": "2",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )
    client.get_minimal_prices("1", "2", start)
    assert api.calls[-1][0] == "get_minimal_pricing"
    with pytest.raises(RzdValidationError, match="earlier"):
        client.get_train_availability("1", "2", end, start)


def test_car_metadata_methods_validate_and_forward(client: RzdClient, api: FakeApi) -> None:
    target = future_date()
    args = (target, "22:30", "001A", "03", "01К", "2Э", "ФПК")
    client.get_car_scheme(*args)
    assert api.calls[-1][0] == "get_car_scheme"
    assert api.calls[-1][1]["departure_date"].endswith("T22:30:00")
    client.get_car_images(*args, car_numeration="FromTail")
    assert api.calls[-1][0] == "get_car_images"
    assert api.calls[-1][1]["car_numeration"] == "FromTail"
    with pytest.raises(RzdValidationError, match="car_number"):
        client.get_car_scheme(target, "22:30", "001A", "", "01К", "2Э", "ФПК")


def test_route_stations_and_client_lifecycle(client: RzdClient, api: FakeApi) -> None:
    target = future_date()
    result = client.get_route_stations("1", "2", target, "22:30", "001A")
    assert result.train_number == "001A"
    assert api.calls[-1][1]["departure_date"].endswith("T22:30:00")
    with pytest.raises(RzdValidationError, match="must not be empty"):
        client.get_route_stations("1", "2", target, "22:30", "")

    client.close()
    client.close()
    assert api.closed is True
    with pytest.raises(RzdValidationError, match="closed"):
        client.find_stations("Москва")


def test_context_manager_closes_api(api: FakeApi) -> None:
    with RzdClient(Config(), _api=api) as client:  # type: ignore[arg-type]
        assert client.resolve_station_code("2000000") == "2000000"
    assert api.closed is True
