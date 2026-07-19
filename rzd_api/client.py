from __future__ import annotations

import time
from collections import OrderedDict
from datetime import date, datetime
from datetime import time as datetime_time
from zoneinfo import ZoneInfo

from .api import RzdApi
from .config import Config
from .exceptions import (
    RzdAmbiguousStationError,
    RzdSchemaError,
    RzdStationNotFoundError,
    RzdValidationError,
)
from .models import CarriageResult, RoundTripResult, RouteStationsResult, Station, TrainRoute

MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")


class RzdClient:
    """Typed high-level client for the ticket.rzd.ru API."""

    def __init__(self, config: Config | None = None, *, _api: RzdApi | None = None) -> None:
        self.config = config or Config()
        self._api = _api or RzdApi(self.config)
        self._station_cache: OrderedDict[tuple[str, str, bool], tuple[float, list[Station]]] = (
            OrderedDict()
        )
        self._closed = False

    def search_tickets(
        self,
        from_station: str | int,
        to_station: str | int,
        departure_date: str | date | datetime,
        return_date: str | date | datetime | None = None,
        *,
        adults: int = 1,
        children: int = 0,
        only_with_seats: bool = True,
        include_transfers: bool = False,
        transport_type: str = "all",
    ) -> list[TrainRoute] | RoundTripResult:
        """Search direct railway routes by station names or codes."""
        self._ensure_open()
        if include_transfers:
            raise NotImplementedError(
                "Transfer routes are not supported by the ticket.rzd.ru v1 pricing endpoint."
            )
        if transport_type != "all":
            if transport_type not in {"trains", "suburban"}:
                raise RzdValidationError("transport_type must be one of: all, suburban, trains.")
            raise NotImplementedError(
                "Transport-type filtering is not supported by the "
                "ticket.rzd.ru v1 pricing endpoint."
            )
        self._validate_passengers(adults, children)

        departure = self._parse_datetime(departure_date, "departure_date")
        return_value = None
        if return_date is not None:
            return_value = self._parse_datetime(return_date, "return_date")
            if return_value < departure:
                raise RzdValidationError("return_date must not be earlier than departure_date.")

        origin = self.resolve_station_code(from_station)
        destination = self.resolve_station_code(to_station)
        if origin == destination:
            raise RzdValidationError("Origin and destination stations must be different.")
        forward = self._api.get_train_routes(
            origin=origin,
            destination=destination,
            departure_date=self._format_datetime(departure),
            adults=adults,
            children=children,
        )
        forward = self._filter_routes(forward, only_with_seats)

        if return_value is None:
            return forward

        back = self._api.get_train_routes(
            origin=destination,
            destination=origin,
            departure_date=self._format_datetime(return_value),
            adults=adults,
            children=children,
        )
        filtered_back = self._filter_routes(back, only_with_seats)
        return RoundTripResult(
            forward=forward,
            back=filtered_back,
            raw={
                "forward": [route.raw for route in forward],
                "back": [route.raw for route in filtered_back],
            },
        )

    def find_stations(
        self,
        query: str,
        *,
        transport_type: str = "rail,suburban",
        group_results: bool = True,
    ) -> list[Station]:
        """Find station candidates without discarding synonym matches."""
        self._ensure_open()
        normalized_query = str(query).strip()
        if len(normalized_query) < 2:
            raise RzdValidationError("Station query must contain at least two characters.")
        if not transport_type.strip():
            raise RzdValidationError("transport_type must not be empty.")

        key = (normalized_query.casefold(), transport_type, group_results)
        cached = self._station_cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] <= self.config.station_cache_ttl:
            self._station_cache.move_to_end(key)
            return list(cached[1])
        if cached:
            del self._station_cache[key]

        stations = self._api.find_stations(
            query=normalized_query,
            transport_type=transport_type,
            group_results=group_results,
        )
        if self.config.station_cache_size > 0 and self.config.station_cache_ttl > 0:
            self._station_cache[key] = (now, list(stations))
            self._station_cache.move_to_end(key)
            while len(self._station_cache) > self.config.station_cache_size:
                self._station_cache.popitem(last=False)
        return stations

    def resolve_station_code(self, station: str | int) -> str:
        """Resolve a numeric code or a unique station name."""
        self._ensure_open()
        value = str(station).strip()
        if not value:
            raise RzdValidationError("Station name or code must not be empty.")
        if value.isdigit():
            return value

        matches = self.find_stations(value)
        if not matches:
            raise RzdStationNotFoundError(value)
        folded = value.casefold()

        exact = self._unique_by_code([item for item in matches if item.name.casefold() == folded])
        if len(exact) == 1:
            return exact[0].code
        if len(exact) > 1:
            raise RzdAmbiguousStationError(value, exact)

        prefix = self._unique_by_code(
            [item for item in matches if item.name.casefold().startswith(folded)]
        )
        if len(prefix) == 1:
            return prefix[0].code
        if len(prefix) > 1:
            raise RzdAmbiguousStationError(value, prefix)

        unique_matches = self._unique_by_code(matches)
        if len(unique_matches) == 1:
            return unique_matches[0].code
        raise RzdAmbiguousStationError(value, unique_matches)

    def get_carriages(
        self,
        from_station: str | int,
        to_station: str | int,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
        *,
        car_number: str = "01",
        provider: str = "P1",
    ) -> CarriageResult:
        """Fetch carriage and availability details for an existing train."""
        self._ensure_open()
        parsed_time = self._parse_time(departure_time)
        departure = self._parse_datetime(
            departure_date,
            "departure_date",
            override_time=parsed_time,
        )
        normalized_train = str(train_number).strip()
        normalized_car = str(car_number).strip()
        normalized_provider = str(provider).strip()
        if not normalized_train or not normalized_car or not normalized_provider:
            raise RzdValidationError("train_number, car_number and provider must not be empty.")
        origin = self.resolve_station_code(from_station)
        destination = self.resolve_station_code(to_station)
        if origin == destination:
            raise RzdValidationError("Origin and destination stations must be different.")

        self._validate_train_exists(
            origin=origin,
            destination=destination,
            departure=departure,
            train_number=normalized_train,
        )
        return self._api.get_carriages(
            origin=origin,
            destination=destination,
            departure_date=self._format_datetime(departure),
            train_number=normalized_train,
            car_number=normalized_car,
            provider=normalized_provider,
        )

    def get_route_stations(self, object_id: str) -> RouteStationsResult:
        """Fetch stations for a route object returned by RZD."""
        self._ensure_open()
        value = str(object_id).strip()
        if not value:
            raise RzdValidationError("object_id must not be empty.")
        return self._api.get_route_stations(object_id=value)

    def _validate_train_exists(
        self,
        *,
        origin: str,
        destination: str,
        departure: datetime,
        train_number: str,
    ) -> None:
        search_date = departure.replace(hour=0, minute=0, second=0, microsecond=0)
        routes = self._api.get_train_routes(
            origin=origin,
            destination=destination,
            departure_date=self._format_datetime(search_date),
            adults=1,
            children=0,
        )
        target_number = self._normalize_train_number(train_number)
        matches = [
            route
            for route in routes
            if self._normalize_train_number(route.number) == target_number
            or self._normalize_train_number(route.display_number or "") == target_number
        ]
        if not matches:
            available = ", ".join(route.number for route in routes[:10]) or "none"
            raise RzdValidationError(
                f"Train {train_number} was not found for the route/date. Available: {available}."
            )

        requested_time = departure.strftime("%H:%M")
        known_times = [
            route.departure_time[11:16]
            for route in matches
            if route.departure_time and len(route.departure_time) >= 16
        ]
        if requested_time not in known_times:
            if not known_times:
                raise RzdSchemaError("Matched train routes contain no departure time.")
            raise RzdValidationError(
                f"Train {train_number} is not available at {requested_time}. "
                f"Available times: {', '.join(known_times)}."
            )

    @staticmethod
    def _filter_routes(routes: list[TrainRoute], only_with_seats: bool) -> list[TrainRoute]:
        if not only_with_seats:
            return routes
        filtered: list[TrainRoute] = []
        for route in routes:
            if route.available_places is None:
                raise RzdSchemaError(
                    f"Cannot determine seat availability for train {route.number}."
                )
            if route.available_places > 0:
                filtered.append(route)
        return filtered

    @staticmethod
    def _validate_passengers(adults: int, children: int) -> None:
        if isinstance(adults, bool) or not isinstance(adults, int) or adults < 1:
            raise RzdValidationError("adults must be an integer greater than zero.")
        if isinstance(children, bool) or not isinstance(children, int) or children < 0:
            raise RzdValidationError("children must be a non-negative integer.")

    @classmethod
    def _parse_datetime(
        cls,
        value: str | date | datetime,
        field_name: str,
        *,
        override_time: datetime_time | None = None,
    ) -> datetime:
        parsed: datetime
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, override_time or datetime_time.min)
        else:
            raw = str(value).strip()
            if not raw:
                raise RzdValidationError(f"{field_name} must not be empty.")
            parsed = cls._parse_datetime_string(raw, field_name)

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(MOSCOW_TIMEZONE).replace(tzinfo=None)
        if override_time is not None:
            parsed = datetime.combine(parsed.date(), override_time)
        today = datetime.now(MOSCOW_TIMEZONE).date()
        if parsed.date() < today:
            raise RzdValidationError(f"{field_name} must not be in the past.")
        return parsed.replace(microsecond=0)

    @staticmethod
    def _parse_datetime_string(raw: str, field_name: str) -> datetime:
        for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, date_format)
            except ValueError:
                pass
        iso_value = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        try:
            return datetime.fromisoformat(iso_value)
        except ValueError as exc:
            raise RzdValidationError(
                f"{field_name} must use DD.MM.YYYY, YYYY-MM-DD or ISO datetime format."
            ) from exc

    @staticmethod
    def _parse_time(value: str) -> datetime_time:
        try:
            return datetime.strptime(str(value).strip(), "%H:%M").time()
        except ValueError as exc:
            raise RzdValidationError("departure_time must use HH:MM format.") from exc

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _normalize_train_number(value: str) -> str:
        return "".join(value.split()).upper()

    @staticmethod
    def _unique_by_code(stations: list[Station]) -> list[Station]:
        return list({station.code: station for station in stations}.values())

    def _ensure_open(self) -> None:
        if self._closed:
            raise RzdValidationError("The RZD client is closed.")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._station_cache.clear()
        self._api.close()

    def __enter__(self) -> RzdClient:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
