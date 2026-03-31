from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .api import Api
from .config import Config
from .query import RzdException


class RzdClient:
    """High-level client for using the package as a Python library."""

    TRANSPORT_TYPES = {
        'trains': 1,
        'suburban': 2,
        'all': 3,
    }

    def __init__(self, config: Config | None = None, api: Api | None = None):
        self.api = api or Api(config)

    def search_tickets(
        self,
        from_station: str | int,
        to_station: str | int,
        departure_date: str | date | datetime,
        return_date: str | date | datetime | None = None,
        *,
        only_with_seats: bool = True,
        include_transfers: bool = False,
        transport_type: str = 'all',
    ) -> list[dict[str, Any]] | dict[str, list[dict[str, Any]]]:
        """Search tickets by station names or station codes."""
        params = {
            'code0': self.resolve_station_code(from_station),
            'code1': self.resolve_station_code(to_station),
            'dt0': self._format_date(departure_date),
            'dir': 1 if return_date is not None else 0,
            'tfl': self._transport_type_code(transport_type),
            'checkSeats': 1 if only_with_seats else 0,
            'md': 1 if include_transfers else 0,
        }

        if return_date is not None:
            params['dt1'] = self._format_date(return_date)
            return self.api.train_routes_return_data(params)

        return self.api.train_routes_data(params)

    def get_carriages(
        self,
        from_station: str | int,
        to_station: str | int,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
    ) -> dict[str, Any]:
        """Fetch carriage information for a train."""
        params = {
            'code0': self.resolve_station_code(from_station),
            'code1': self.resolve_station_code(to_station),
            'dt0': self._format_date(departure_date),
            'time0': departure_time,
            'tnum0': train_number,
            'dir': 0,
        }
        return self.api.train_carriages_data(params)

    def get_route_stations(
        self,
        train_number: str,
        departure_date: str | date | datetime,
    ) -> dict[str, Any]:
        """Fetch all stations for a train route."""
        return self.api.train_station_list_data({
            'trainNumber': train_number,
            'depDate': self._format_date(departure_date),
        })

    def find_stations(self, query: str, *, compact_mode: str = 'y') -> list[dict[str, str]]:
        """Find stations by a partial name."""
        return self.api.station_code_data({
            'stationNamePart': query,
            'compactMode': compact_mode,
        })

    def resolve_station_code(self, station: str | int) -> str:
        """Resolve either a station code or a station name to a code."""
        value = str(station).strip()
        if not value:
            raise ValueError('Station name or code must not be empty.')

        if value.isdigit():
            return value

        matches = self.find_stations(value)
        if not matches:
            raise RzdException(f'Station not found: {value}')

        upper_value = value.upper()
        exact_match = next((item for item in matches if item['station'].upper() == upper_value), None)
        if exact_match:
            return exact_match['code']

        return matches[0]['code']

    def _format_date(self, value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.strftime('%d.%m.%Y')
        if isinstance(value, date):
            return value.strftime('%d.%m.%Y')
        return value

    def _transport_type_code(self, transport_type: str) -> int:
        try:
            return self.TRANSPORT_TYPES[transport_type]
        except KeyError as exc:
            allowed = ', '.join(sorted(self.TRANSPORT_TYPES))
            raise ValueError(
                f'Unsupported transport_type: {transport_type}. Use one of: {allowed}.'
            ) from exc
