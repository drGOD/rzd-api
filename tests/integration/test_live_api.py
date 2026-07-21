from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest

from rzd_api import RzdClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RZD_LIVE_TEST") != "1",
        reason="Set RZD_LIVE_TEST=1 to call the live ticket.rzd.ru API.",
    ),
]


def test_live_station_and_direct_route_search() -> None:
    departure = date.today() + timedelta(days=14)
    with RzdClient() as client:
        stations = client.find_stations("Москва")
        assert stations
        routes = client.search_tickets(
            "2000000",
            "2004000",
            departure,
            only_with_seats=False,
        )
        assert isinstance(routes, list)


def test_live_current_calendar_carriage_and_route_contracts() -> None:
    start = date.today() + timedelta(days=3)
    end = start + timedelta(days=30)
    with RzdClient() as client:
        availability = client.get_train_availability("2000000", "2004000", start, end)
        assert availability.origin_code == "2000000"
        assert availability.items

        minimal_prices = client.get_minimal_prices("2000000", "2004000", start)
        assert minimal_prices.prices

        routes = client.search_tickets("2000000", "2004000", start, only_with_seats=False)
        assert isinstance(routes, list)
        assert routes
        route = routes[0]
        assert route.departure_time
        departure = datetime.fromisoformat(route.departure_time.replace("Z", "+00:00"))
        origin = route.origin_code or "2000000"
        destination = route.destination_code or "2004000"
        train_number = route.route_number or route.number

        carriages = client.get_carriages(
            origin,
            destination,
            departure.date(),
            departure.strftime("%H:%M"),
            train_number,
            provider=route.provider or "P1",
        )
        assert carriages.cars

        train_route = client.get_route_stations(
            origin,
            destination,
            departure.date(),
            departure.strftime("%H:%M"),
            train_number,
            provider=route.provider or "P1",
        )
        assert train_route.stations
