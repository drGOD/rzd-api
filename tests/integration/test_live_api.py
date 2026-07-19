from __future__ import annotations

import os
from datetime import date, timedelta

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
