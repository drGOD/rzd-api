#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


BASE_URL = "https://ticket.rzd.ru/api/v1"


@dataclass
class Station:
    name: str
    code: str


def _first_non_empty(source: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _iter_dict_nodes(payload: Any):
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _iter_dict_nodes(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_dict_nodes(item)


def _request_json(
    session: requests.Session,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 25.0,
) -> tuple[bool, int | None, Any]:
    url = f"{BASE_URL}{path}"
    try:
        response = session.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return False, None, {"error": str(exc), "path": path}

    content_type = response.headers.get("Content-Type", "")
    try:
        payload = response.json()
        is_json = True
    except ValueError:
        payload = {
            "raw": response.text[:1200],
            "path": path,
            "content_type": content_type,
            "parse_error": "Response is not valid JSON",
        }
        is_json = False

    ok = 200 <= response.status_code < 300 and is_json
    return ok, response.status_code, payload


def _extract_stations(payload: Any, query: str) -> list[Station]:
    stations: list[Station] = []
    for node in _iter_dict_nodes(payload):
        code = _first_non_empty(node, ["ExpressCode", "expressCode", "code", "Code", "c"])
        name = _first_non_empty(node, ["NameRu", "nameRu", "name", "Name", "n", "title"])
        if not code or not name:
            continue
        station_name = str(name).strip()
        if query and query.upper() not in station_name.upper():
            continue
        stations.append(Station(name=station_name, code=str(code)))

    unique: dict[tuple[str, str], Station] = {}
    for st in stations:
        unique[(st.name, st.code)] = st
    return list(unique.values())


def _choose_station(candidates: list[Station], query: str) -> Station | None:
    if not candidates:
        return None
    exact = [s for s in candidates if s.name.upper() == query.upper()]
    if exact:
        return exact[0]
    starts = [s for s in candidates if s.name.upper().startswith(query.upper())]
    if starts:
        numeric = [s for s in starts if s.code.isdigit()]
        return numeric[0] if numeric else starts[0]

    numeric = [s for s in candidates if s.code.isdigit()]
    return numeric[0] if numeric else candidates[0]


def _extract_trains(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        direct_lists = []
        for key in ("Trains", "trains", "TrainList", "trainList", "items", "Items"):
            value = payload.get(key)
            if isinstance(value, list):
                direct_lists.append(value)
        if direct_lists:
            trains = [item for lst in direct_lists for item in lst if isinstance(item, dict)]
            if trains:
                return trains

    trains: list[dict[str, Any]] = []
    for node in _iter_dict_nodes(payload):
        train_no = _first_non_empty(
            node,
            ["TrainNumber", "displayTrainNumber", "hiddenTrainNumber"],
        )
        departure = _first_non_empty(
            node,
            ["DepartureDateTime", "departureDateTime", "departureDate", "DepartureDate"],
        )
        arrival = _first_non_empty(
            node,
            ["ArrivalDateTime", "arrivalDateTime", "arrivalDate", "ArrivalDate"],
        )
        if train_no and (departure or arrival or "CarGroups" in node):
            trains.append(node)
    return trains


def _normalize_train(train: dict[str, Any]) -> dict[str, Any]:
    number = _first_non_empty(
        train,
        ["TrainNumber", "displayTrainNumber", "hiddenTrainNumber"],
    )
    departure = _first_non_empty(
        train,
        ["DepartureDateTime", "departureDateTime", "departureDate", "DepartureDate"],
    )
    arrival = _first_non_empty(
        train,
        ["ArrivalDateTime", "arrivalDateTime", "arrivalDate", "ArrivalDate"],
    )
    min_price = _first_non_empty(
        train,
        ["MinPrice", "minPrice", "priceFrom", "PriceFrom", "TotalPrice", "totalPrice"],
    )
    route_from = _first_non_empty(train, ["OriginStationName", "originStationName", "From"])
    route_to = _first_non_empty(train, ["DestinationStationName", "destinationStationName", "To"])
    return {
        "train_number": number,
        "departure": departure,
        "arrival": arrival,
        "from": route_from,
        "to": route_to,
        "min_price": min_price,
    }


def _run_step(name: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{now}] {name}")


def _collect_payload_diagnostics(payload: Any) -> dict[str, Any]:
    diag: dict[str, Any] = {}
    if isinstance(payload, dict):
        diag["top_level_keys"] = list(payload.keys())[:30]
        counts: dict[str, int] = {}
        for key in ("Trains", "trains", "TrainList", "items", "tp"):
            value = payload.get(key)
            if isinstance(value, list):
                counts[key] = len(value)
        if counts:
            diag["list_counts"] = counts
    return diag


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sequential end-to-end user journey test for ticket.rzd.ru/api/v1."
    )
    parser.add_argument("--from-query", default="Москва", help="Departure station search query.")
    parser.add_argument("--to-query", default="Санкт-Петербург", help="Arrival station search query.")
    parser.add_argument(
        "--depart-date",
        default=(datetime.now()).strftime("%Y-%m-%d"),
        help="Forward date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--return-date",
        required=True,
        help="Backward date in YYYY-MM-DD.",
    )
    parser.add_argument("--language", default="ru", help="API language.")
    parser.add_argument("--timeout", type=float, default=25.0, help="Timeout in seconds.")
    parser.add_argument("--proxy", default=None, help="Optional proxy URL.")
    parser.add_argument("--x-client-id", default="22900", help="Optional X-Client-ID.")
    parser.add_argument("--x-ksid-bsid", default=None, help="Optional X-Ksid-Bsid.")
    parser.add_argument("--cookie", default=None, help="Optional Cookie header.")
    parser.add_argument("--auth-bearer", default=None, help="Optional Bearer token.")
    parser.add_argument("--max-trains", type=int, default=5, help="How many trains to show per direction.")
    parser.add_argument(
        "--save-responses-dir",
        default=None,
        help="Optional directory to save raw JSON responses for debugging.",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Referer": "https://ticket.rzd.ru/",
        }
    )
    if args.x_client_id:
        session.headers["X-Client-ID"] = args.x_client_id
    if args.x_ksid_bsid:
        session.headers["X-Ksid-Bsid"] = args.x_ksid_bsid
        session.headers["X-Ksid-Approved"] = args.x_ksid_bsid
    if args.cookie:
        session.headers["Cookie"] = args.cookie
    if args.auth_bearer:
        session.headers["Authorization"] = f"Bearer {args.auth_bearer}"
    if args.proxy:
        session.proxies.update({"http": args.proxy, "https": args.proxy})
    if args.save_responses_dir:
        os.makedirs(args.save_responses_dir, exist_ok=True)

    def save_payload(name: str, payload: Any) -> None:
        if not args.save_responses_dir:
            return
        path = os.path.join(args.save_responses_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    _run_step("1/5 Поиск станции отправления")
    ok, code, payload = _request_json(
        session,
        "GET",
        "/suggests",
        params={
            "Query": args.from_query,
            "TransportType": "rail,suburban",
            "GroupResults": "true",
            "RailwaySortPriority": "true",
            "SynonymOn": 1,
            "Language": args.language,
        },
        timeout=args.timeout,
    )
    if not ok:
        print(json.dumps({"step": "from_station_search", "http": code, "payload": payload}, ensure_ascii=False, indent=2))
        return 1
    save_payload("1_from_station_search", payload)
    from_candidates = _extract_stations(payload, args.from_query)
    from_station = _choose_station(from_candidates, args.from_query)
    if not from_station:
        print("Не удалось найти станцию отправления.")
        return 1
    print(f"Выбрано: {from_station.name} ({from_station.code})")

    _run_step("2/5 Поиск станции прибытия")
    ok, code, payload = _request_json(
        session,
        "GET",
        "/suggests",
        params={
            "Query": args.to_query,
            "TransportType": "rail,suburban",
            "GroupResults": "true",
            "RailwaySortPriority": "true",
            "SynonymOn": 1,
            "Language": args.language,
        },
        timeout=args.timeout,
    )
    if not ok:
        print(json.dumps({"step": "to_station_search", "http": code, "payload": payload}, ensure_ascii=False, indent=2))
        return 1
    save_payload("2_to_station_search", payload)
    to_candidates = _extract_stations(payload, args.to_query)
    to_station = _choose_station(to_candidates, args.to_query)
    if not to_station:
        print("Не удалось найти станцию прибытия.")
        return 1
    print(f"Выбрано: {to_station.name} ({to_station.code})")

    _run_step("3/5 Поиск билетов туда")
    ok, code, payload = _request_json(
        session,
        "GET",
        "/railway-service/prices/train-pricing",
        params={
            "service_provider": "B2B_RZD",
            "getByLocalTime": "true",
            "carGrouping": "DontGroup",
            "origin": from_station.code,
            "destination": to_station.code,
            "departureDate": f"{args.depart_date}T00:00:00",
            "specialPlacesDemand": "StandardPlacesAndForDisabledPersons",
            "carIssuingType": "Passenger",
            "getTrainsFromSchedule": "true",
            "adultPassengersQuantity": 1,
            "childrenPassengersQuantity": 0,
            "hasPlacesForLargeFamily": "false",
        },
        timeout=args.timeout,
    )
    if not ok:
        print(json.dumps({"step": "forward_search", "http": code, "payload": payload}, ensure_ascii=False, indent=2))
        return 1
    save_payload("3_forward_search", payload)
    forward_trains_raw = _extract_trains(payload)
    forward_trains = [_normalize_train(t) for t in forward_trains_raw[: args.max_trains]]
    print(f"Найдено рейсов (приблизительно): {len(forward_trains_raw)}")
    if not forward_trains_raw:
        print("Диагностика ответа (туда):")
        print(json.dumps(_collect_payload_diagnostics(payload), ensure_ascii=False, indent=2))

    _run_step("4/5 Поиск билетов обратно")
    ok, code, payload = _request_json(
        session,
        "GET",
        "/railway-service/prices/train-pricing",
        params={
            "service_provider": "B2B_RZD",
            "getByLocalTime": "true",
            "carGrouping": "DontGroup",
            "origin": to_station.code,
            "destination": from_station.code,
            "departureDate": f"{args.return_date}T00:00:00",
            "specialPlacesDemand": "StandardPlacesAndForDisabledPersons",
            "carIssuingType": "Passenger",
            "getTrainsFromSchedule": "true",
            "adultPassengersQuantity": 1,
            "childrenPassengersQuantity": 0,
            "hasPlacesForLargeFamily": "false",
        },
        timeout=args.timeout,
    )
    if not ok:
        print(json.dumps({"step": "backward_search", "http": code, "payload": payload}, ensure_ascii=False, indent=2))
        return 1
    save_payload("4_backward_search", payload)
    backward_trains_raw = _extract_trains(payload)
    backward_trains = [_normalize_train(t) for t in backward_trains_raw[: args.max_trains]]
    print(f"Найдено рейсов (приблизительно): {len(backward_trains_raw)}")
    if not backward_trains_raw:
        print("Диагностика ответа (обратно):")
        print(json.dumps(_collect_payload_diagnostics(payload), ensure_ascii=False, indent=2))

    _run_step("5/5 Сводка пользовательского пути")
    report = {
        "search": {
            "from": {"query": args.from_query, "name": from_station.name, "code": from_station.code},
            "to": {"query": args.to_query, "name": to_station.name, "code": to_station.code},
            "dates": {"depart": args.depart_date, "return": args.return_date},
        },
        "results": {
            "forward_count_estimate": len(forward_trains_raw),
            "backward_count_estimate": len(backward_trains_raw),
            "forward_preview": forward_trains,
            "backward_preview": backward_trains,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
