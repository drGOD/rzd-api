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
    node_id: str | None = None
    node_type: str | None = None
    transport_type: str | None = None
    region: str | None = None


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
    route_number: str | None = None
    origin_code: str | None = None
    destination_code: str | None = None
    provider: str | None = None


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
    max_price: float | None = None
    service_cost: float | None = None
    car_sub_type: str | None = None
    car_type_name: str | None = None
    service_class: str | None = None
    service_class_name: str | None = None
    scheme_id: int | None = None
    scheme_name: str | None = None
    carrier: str | None = None
    carrier_display_name: str | None = None
    direction: str | None = None
    numeration: str | None = None
    train_number: str | None = None
    free_places: str | None = None
    services: list[str] = field(default_factory=list)
    has_images: bool | None = None


@dataclass(slots=True)
class CarriageResult(ModelMixin):
    cars: list[Carriage] = field(default_factory=list)
    train_number: str | None = None
    origin_code: str | None = None
    destination_code: str | None = None
    departure_time: str | None = None
    route_policy: str | None = None
    booking_system: str | None = None
    allowed_document_types: list[str] = field(default_factory=list)
    origin_retrieval_date: str | None = None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class TrainAvailability(ModelMixin):
    date: str
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class TrainAvailabilityResult(ModelMixin):
    origin_code: str
    destination_code: str
    items: list[TrainAvailability] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class MinimalPrice(ModelMixin):
    date: str
    min_price: float | None
    disabled_place_min_price: float | None
    carriers: list[JsonObject] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class MinimalPricingResult(ModelMixin):
    origin_code: str
    destination_code: str
    prices: list[MinimalPrice] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class CarScheme(ModelMixin):
    scheme_id: int | None
    car_sub_type: str | None
    start_date: str | None
    end_date: str | None
    train_number: str | None
    carrier: str | None
    car_number: str | None
    service_class: str | None
    first_storey: str | None
    second_storey: str | None
    mobile_first_storey: str | None
    mobile_second_storey: str | None
    direction: str | None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class CarImage(ModelMixin):
    image_id: int | None
    title_ru: str | None
    title_en: str | None
    preview: str | None
    content: str | None
    sequence_number: int | None
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class CarImagesResult(ModelMixin):
    scheme_id: int | None
    car_sub_type: str | None
    images: list[CarImage] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class RouteStation(ModelMixin):
    name: str | None
    code: str | None
    arrival_time: str | None
    departure_time: str | None
    distance: int | None
    raw: JsonObject = field(default_factory=dict)
    city_name: str | None = None
    local_arrival_time: str | None = None
    local_departure_time: str | None = None
    stop_duration: float | None = None
    time_description: str | None = None
    days_from_origin: int | None = None
    time_zone_difference: int | None = None
    actual_movement: bool | None = None
    is_cutaway_station: bool | None = None


@dataclass(slots=True)
class RouteStationsResult(ModelMixin):
    train_number: str | None
    stations: list[RouteStation] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)
    route_name: str | None = None
    origin_name: str | None = None
    destination_name: str | None = None
