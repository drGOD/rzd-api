from __future__ import annotations

import pytest

import rzd_api
from rzd_api import (
    CarGroup,
    Config,
    RoundTripResult,
    RzdAmbiguousStationError,
    RzdHTTPError,
    RzdStationNotFoundError,
    RzdTransportError,
    RzdValidationError,
    TrainRoute,
)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"language": "de"},
        {"base_url": "relative"},
        {"connect_timeout": 0},
        {"read_timeout": -1},
        {"retry_total": -1},
        {"retry_backoff": -1},
        {"station_cache_ttl": -1},
        {"station_cache_size": -1},
        {"base_url": None},
        {"connect_timeout": True},
        {"retry_total": 1.5},
        {"retry_backoff": "slow"},
        {"station_cache_ttl": "forever"},
        {"station_cache_size": True},
        {"proxy": 1},
    ],
)
def test_config_validation(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Config(**kwargs)  # type: ignore[arg-type]


def test_models_serialize_recursively() -> None:
    group = CarGroup("Compartment", 1200.0, 2, {"raw": True})
    route = TrainRoute("001A", None, None, None, None, None, 1200.0, 2, [group], {"train": True})
    result = RoundTripResult([route], [], {"forward": [{"train": True}], "back": []})
    serialized = result.to_dict()
    assert serialized["forward"][0]["car_groups"][0]["available_places"] == 2
    assert serialized["forward"][0]["raw"] == {"train": True}
    assert serialized["raw"]["forward"] == [{"train": True}]


def test_exception_hierarchy() -> None:
    assert issubclass(RzdHTTPError, RzdTransportError)
    assert issubclass(RzdStationNotFoundError, RzdValidationError)
    assert issubclass(RzdAmbiguousStationError, RzdValidationError)


def test_public_api_excludes_legacy_symbols_and_config_fields() -> None:
    assert "Api" not in rzd_api.__all__
    assert "Query" not in rzd_api.__all__
    assert not hasattr(rzd_api, "Api")
    assert not hasattr(rzd_api, "Query")
    with pytest.raises(TypeError):
        Config(timeout=5)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Config(debug=True)  # type: ignore[call-arg]
