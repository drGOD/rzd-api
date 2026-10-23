from __future__ import annotations

import json
from typing import Any

import anyio
import pytest

from mcp_server import server
from mcp_server.serialization import serialize
from rzd_api import CarGroup, CarriageResult, TrainRoute, TrainSearchResult


def train() -> TrainRoute:
    return TrainRoute(
        "001А",
        None,
        "Москва",
        "Петербург",
        None,
        None,
        1234.0,
        4,
        car_groups=[CarGroup("Compartment", 1234.0, 4, {"TotalPlaceQuantity": 4})],
        raw={"TrainNumber": "001А", "CarGroups": [{"TotalPlaceQuantity": 4}]},
    )


def test_compact_serialization_preserves_python_models_and_typed_fields() -> None:
    item = train()
    original = item.to_dict()
    compact = serialize(item)
    assert "raw" not in compact
    assert "raw" not in compact["car_groups"][0]
    assert compact["car_groups"][0]["available_places"] == 4
    assert serialize(item, include_raw=True) == original
    assert item.to_dict() == original
    assert serialize({"raw_data": "kept", "values": ({"raw": "hidden", "id": 1},)}) == {
        "raw_data": "kept",
        "values": [{"id": 1}],
    }


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("search_tickets", ("1", "2", "2099-01-01")),
        ("find_stations", ("Москва",)),
        ("get_carriages", ("1", "2", "2099-01-01", "10:00", "001А")),
        ("get_train_availability", ("1", "2", "2099-01-01", "2099-01-10")),
        ("get_minimal_prices", ("1", "2", "2099-01-01")),
        ("get_car_scheme", ("2099-01-01", "10:00", "001А", "01", "К", "2Э", "ФПК")),
        ("get_car_images", ("2099-01-01", "10:00", "001А", "01", "К", "2Э", "ФПК")),
        ("get_route_stations", ("1", "2", "2099-01-01", "10:00", "001А")),
    ],
)
def test_every_mcp_tool_hides_raw_by_default_and_can_return_it(
    monkeypatch: pytest.MonkeyPatch, name: str, args: tuple[Any, ...]
) -> None:
    payload = (
        [train()]
        if name in {"search_tickets", "find_stations"}
        else CarriageResult(raw={"large_upstream": "preserved"})
    )

    class FakeClient:
        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def __getattr__(self, method: str) -> Any:
            def call(*args: Any, **kwargs: Any) -> Any:
                assert method == name
                assert "include_raw" not in kwargs
                return payload

            return call

    monkeypatch.setattr(server, "RzdClient", FakeClient)
    tool = getattr(server, name)
    compact = tool(*args)
    full = tool(*args, include_raw=True)
    assert '"raw":' not in json.dumps(compact)
    assert '"raw":' in json.dumps(full)
    assert full == serialize(payload, include_raw=True)


def test_mcp_search_can_return_completeness_without_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    result = TrainSearchResult(trains=[], partial=True, raw={"NotAllTrainsReturned": True})

    class FakeClient:
        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def search_tickets_detailed(self, *args: Any, **kwargs: Any) -> TrainSearchResult:
            return result

    monkeypatch.setattr(server, "RzdClient", FakeClient)
    compact = server.search_tickets("1", "2", "2099-01-01", include_metadata=True)
    assert isinstance(compact, dict)
    assert compact["partial"] is True
    assert compact["trains"] == []
    assert "raw" not in compact


def test_mcp_publishes_raw_opt_in_on_every_tool() -> None:
    tools = anyio.run(server.create_mcp_app().list_tools)
    assert len(tools) == 8
    for tool in tools:
        assert tool.inputSchema["properties"]["include_raw"]["default"] is False
    search = next(tool for tool in tools if tool.name == "search_tickets")
    assert search.inputSchema["properties"]["include_metadata"]["default"] is False
