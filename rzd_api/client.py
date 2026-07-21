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
from .models import (
    CarImagesResult,
    CarriageResult,
    CarScheme,
    MinimalPricingResult,
    RoundTripResult,
    RouteStationsResult,
    Station,
    TrainAvailabilityResult,
    TrainRoute,
)

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

    def get_train_availability(
        self,
        from_station: str | int,
        to_station: str | int,
        date_from: str | date | datetime,
        date_to: str | date | datetime,
    ) -> TrainAvailabilityResult:
        """Return dates on which RZD reports trains for the selected direction."""
        self._ensure_open()
        start = self._parse_datetime(date_from, "date_from")
        end = self._parse_datetime(date_to, "date_to")
        if end < start:
            raise RzdValidationError("date_to must not be earlier than date_from.")
        origin, destination = self._resolve_direction(from_station, to_station)
        return self._api.get_train_availability(
            origin=origin,
            destination=destination,
            date_from=start.date().isoformat(),
            date_to=end.date().isoformat(),
        )

    def get_minimal_prices(
        self,
        from_station: str | int,
        to_station: str | int,
        date_from: str | date | datetime,
    ) -> MinimalPricingResult:
        """Return the minimum prices published by RZD from a selected date."""
        self._ensure_open()
        start = self._parse_datetime(date_from, "date_from")
        origin, destination = self._resolve_direction(from_station, to_station)
        return self._api.get_minimal_pricing(
            origin=origin,
            destination=destination,
            date_from=start.date().isoformat(),
        )

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
        normalized_provider = str(provider).strip()
        if not normalized_train or not normalized_provider:
            raise RzdValidationError("train_number and provider must not be empty.")
        origin, destination = self._resolve_direction(from_station, to_station)
        return self._api.get_carriages(
            origin=origin,
            destination=destination,
            departure_date=self._format_datetime(departure),
            train_number=normalized_train,
            provider=normalized_provider,
        )

    def get_car_scheme(
        self,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
        car_number: str,
        car_sub_type: str,
        service_class: str,
        carrier: str,
        *,
        car_numeration: str = "FromHead",
    ) -> CarScheme:
        """Fetch the scheme metadata for a carriage returned by ``get_carriages``."""
        self._ensure_open()
        params = self._car_metadata_input(
            departure_date=departure_date,
            departure_time=departure_time,
            train_number=train_number,
            car_number=car_number,
            car_sub_type=car_sub_type,
            service_class=service_class,
            carrier=carrier,
            car_numeration=car_numeration,
        )
        return self._api.get_car_scheme(**params)

    def get_car_images(
        self,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
        car_number: str,
        car_sub_type: str,
        service_class: str,
        carrier: str,
        *,
        car_numeration: str = "FromHead",
    ) -> CarImagesResult:
        """Fetch image metadata for a carriage returned by ``get_carriages``."""
        self._ensure_open()
        params = self._car_metadata_input(
            departure_date=departure_date,
            departure_time=departure_time,
            train_number=train_number,
            car_number=car_number,
            car_sub_type=car_sub_type,
            service_class=service_class,
            carrier=carrier,
            car_numeration=car_numeration,
        )
        return self._api.get_car_images(**params)

    def get_route_stations(
        self,
        from_station: str | int,
        to_station: str | int,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
        *,
        provider: str = "P1",
    ) -> RouteStationsResult:
        """Fetch all stops for a train and direction."""
        self._ensure_open()
        departure = self._parse_datetime(
            departure_date,
            "departure_date",
            override_time=self._parse_time(departure_time),
        )
        normalized_train = str(train_number).strip()
        normalized_provider = str(provider).strip()
        if not normalized_train or not normalized_provider:
            raise RzdValidationError("train_number and provider must not be empty.")
        origin, destination = self._resolve_direction(from_station, to_station)
        return self._api.get_route_stations(
            origin=origin,
            destination=destination,
            departure_date=self._format_datetime(departure),
            train_number=normalized_train,
            provider=normalized_provider,
        )

    def _resolve_direction(self, from_station: str | int, to_station: str | int) -> tuple[str, str]:
        origin = self.resolve_station_code(from_station)
        destination = self.resolve_station_code(to_station)
        if origin == destination:
            raise RzdValidationError("Origin and destination stations must be different.")
        return origin, destination

    def _car_metadata_input(
        self,
        *,
        departure_date: str | date | datetime,
        departure_time: str,
        train_number: str,
        car_number: str,
        car_sub_type: str,
        service_class: str,
        carrier: str,
        car_numeration: str,
    ) -> dict[str, str]:
        departure = self._parse_datetime(
            departure_date,
            "departure_date",
            override_time=self._parse_time(departure_time),
        )
        values = {
            "train_number": str(train_number).strip(),
            "car_number": str(car_number).strip(),
            "car_sub_type": str(car_sub_type).strip(),
            "service_class": str(service_class).strip(),
            "carrier": str(carrier).strip(),
            "car_numeration": str(car_numeration).strip(),
        }
        empty = [name for name, value in values.items() if not value]
        if empty:
            raise RzdValidationError(f"{', '.join(empty)} must not be empty.")
        return {"departure_date": self._format_datetime(departure), **values}

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
