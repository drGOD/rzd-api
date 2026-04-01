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
        _ = only_with_seats
        _ = include_transfers
        _ = self._transport_type_code(transport_type)
        params = {
            'origin': self.resolve_station_code(from_station),
            'destination': self.resolve_station_code(to_station),
            'departureDate': self._to_iso_datetime(departure_date),
            'adultPassengersQuantity': 1,
            'childrenPassengersQuantity': 0,
        }

        if return_date is not None:
            params['returnDate'] = self._to_iso_datetime(return_date)
            return self.api.train_routes_return_data(params)

        return self.api.train_routes_data(params)

    def get_carriages(
        self,
        from_station: str | int,
        to_station: str | int,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
        *,
        car_number: str = '01',
        provider: str = 'P1',
    ) -> dict[str, Any]:
        """Fetch carriage information for a train and specific carriage."""
        origin = self.resolve_station_code(from_station)
        destination = self.resolve_station_code(to_station)
        departure_dt = self._to_iso_datetime(departure_date, departure_time)

        self._validate_train_exists(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            departure_time=departure_time,
            train_number=train_number,
        )

        params = {
            'OriginCode': origin,
            'DestinationCode': destination,
            'DepartureDate': departure_dt,
            'TrainNumber': train_number,
            'CarNumber': car_number,
            'Provider': provider,
        }
        return self.api.train_carriages_data(params)

    def get_route_stations(
        self,
        object_id: str,
    ) -> dict[str, Any]:
        """Fetch all stations for a train route."""
        return self.api.train_station_list_data({
            'id': object_id,
        })

    def find_stations(
        self,
        query: str,
        *,
        transport_type: str = 'rail,suburban',
        group_results: bool = True,
    ) -> list[dict[str, str]]:
        """Find stations by a partial name."""
        return self.api.station_code_data({
            'stationNamePart': query,
            'transportType': transport_type,
            'groupResults': group_results,
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

    def _to_iso_datetime(self, value: str | date | datetime, time_value: str | None = None) -> str:
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M:%S')
        if isinstance(value, date):
            if time_value:
                parsed_time = datetime.strptime(time_value, '%H:%M').time()
                return datetime.combine(value, parsed_time).strftime('%Y-%m-%dT%H:%M:%S')
            return value.strftime('%Y-%m-%dT00:00:00')

        raw = str(value).strip()
        if 'T' in raw:
            return raw
        try:
            parsed = datetime.strptime(raw, '%d.%m.%Y')
            if time_value:
                parsed_time = datetime.strptime(time_value, '%H:%M').time()
                parsed = datetime.combine(parsed.date(), parsed_time)
            return parsed.strftime('%Y-%m-%dT%H:%M:%S')
        except ValueError:
            return raw

    def _transport_type_code(self, transport_type: str) -> int:
        try:
            return self.TRANSPORT_TYPES[transport_type]
        except KeyError as exc:
            allowed = ', '.join(sorted(self.TRANSPORT_TYPES))
            raise ValueError(
                f'Unsupported transport_type: {transport_type}. Use one of: {allowed}.'
            ) from exc

    def _validate_train_exists(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
    ) -> None:
        trains = self.api.train_routes_data({
            'origin': origin,
            'destination': destination,
            'departureDate': self._to_iso_datetime(departure_date),
            'adultPassengersQuantity': 1,
            'childrenPassengersQuantity': 0,
        })

        normalized_target = self._normalize_train_number(train_number)
        requested_time = departure_time.strip()[:5]

        matched_by_number: list[dict[str, Any]] = []
        for train in trains:
            current_number = self._normalize_train_number(
                str(train.get('TrainNumber') or train.get('DisplayTrainNumber') or ''),
            )
            if current_number == normalized_target:
                matched_by_number.append(train)

        if not matched_by_number:
            available = [
                str(t.get('TrainNumber') or t.get('DisplayTrainNumber') or '?')
                for t in trains[:10]
            ]
            raise RzdException(
                f'Train {train_number} is not found for selected route/date. '
                f'Available examples: {", ".join(available) if available else "none"}.'
            )

        for train in matched_by_number:
            dep = str(train.get('DepartureDateTime') or train.get('LocalDepartureDateTime') or '')
            if not dep:
                return
            time_part = dep[11:16] if len(dep) >= 16 else ''
            if time_part == requested_time:
                return

        available_times = []
        for train in matched_by_number:
            dep = str(train.get('DepartureDateTime') or train.get('LocalDepartureDateTime') or '')
            if len(dep) >= 16:
                available_times.append(dep[11:16])
        raise RzdException(
            f'Train {train_number} is found, but not at {requested_time}. '
            f'Available times: {", ".join(available_times) if available_times else "unknown"}.'
        )

    def _normalize_train_number(self, value: str) -> str:
        return ''.join(value.split()).upper()
