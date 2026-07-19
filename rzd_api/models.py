from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, cast

JsonObject = dict[str, Any]


class ModelMixin:
    """Shared serialization helper for public response models."""

    def to_dict(self) -> JsonObject:
        return asdict(cast(Any, self))


@dataclass(slots=True)
class Station(ModelMixin):
    name: str
    code: str
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class CarGroup(ModelMixin):
    car_type: str | None
    min_price: float | None
    available_places: int | None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class TrainRoute(ModelMixin):
    number: str
    display_number: str | None
    origin_name: str | None
    destination_name: str | None
    departure_time: str | None
    arrival_time: str | None
    min_price: float | None
    available_places: int | None
    car_groups: list[CarGroup] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class RoundTripResult(ModelMixin):
    forward: list[TrainRoute] = field(default_factory=list)
    back: list[TrainRoute] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class Carriage(ModelMixin):
    number: str | None
    car_type: str | None
    min_price: float | None
    available_places: int | None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class CarriageResult(ModelMixin):
    cars: list[Carriage] = field(default_factory=list)
    function_blocks: Any = None
    schemes: Any = None
    companies: Any = None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class RouteStation(ModelMixin):
    name: str | None
    code: str | None
    arrival_time: str | None
    departure_time: str | None
    distance: int | None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class RouteStationsResult(ModelMixin):
    train_number: str | None
    stations: list[RouteStation] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)
