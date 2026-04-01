#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from itertools import product
from typing import Any

import requests


BASE_URL = "https://ticket.rzd.ru/api/v1/railway-service/prices/train-pricing"


def make_session(
    x_client_id: str | None,
    x_ksid_bsid: str | None,
    cookie: str | None,
    auth_bearer: str | None,
    proxy: str | None,
) -> requests.Session:
    s = requests.Session()
    s.headers.update(
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
    if x_client_id:
        s.headers["X-Client-ID"] = x_client_id
    if x_ksid_bsid:
        s.headers["X-Ksid-Bsid"] = x_ksid_bsid
        s.headers["X-Ksid-Approved"] = x_ksid_bsid
    if cookie:
        s.headers["Cookie"] = cookie
    if auth_bearer:
        s.headers["Authorization"] = f"Bearer {auth_bearer}"
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    return s


def build_params(
    origin: str,
    destination: str,
    date: str,
    *,
    service_provider: str | None,
    get_by_local_time: bool,
    car_grouping: str,
    special_places_demand: str,
    car_issuing_type: str | None,
    get_trains_from_schedule: bool,
    adults: int,
    children: int,
    has_places_for_large_family: bool,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "getByLocalTime": str(get_by_local_time).lower(),
        "carGrouping": car_grouping,
        "origin": origin,
        "destination": destination,
        "departureDate": f"{date}T00:00:00",
        "specialPlacesDemand": special_places_demand,
        "getTrainsFromSchedule": str(get_trains_from_schedule).lower(),
        "adultPassengersQuantity": adults,
        "childrenPassengersQuantity": children,
        "hasPlacesForLargeFamily": str(has_places_for_large_family).lower(),
    }
    if service_provider:
        params["service_provider"] = service_provider
    if car_issuing_type:
        params["carIssuingType"] = car_issuing_type
    return params


def run_search(
    session: requests.Session,
    params: dict[str, Any],
    timeout: float,
) -> tuple[bool, int | None, dict[str, Any], str]:
    try:
        resp = session.get(BASE_URL, params=params, timeout=timeout)
    except requests.RequestException as exc:
        return False, None, {"error": str(exc)}, BASE_URL

    url = resp.url
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": resp.text[:1500], "content_type": resp.headers.get("Content-Type", "")}
    ok = 200 <= resp.status_code < 300 and isinstance(payload, dict)
    return ok, resp.status_code, payload, url


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    trains = payload.get("Trains")
    err = payload.get("errorInfo")
    return {
        "trains_count": len(trains) if isinstance(trains, list) else None,
        "error_code": err.get("Code") if isinstance(err, dict) else None,
        "error_message": err.get("Message") if isinstance(err, dict) else None,
        "top_keys": list(payload.keys())[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Focused ticket search tester for ticket.rzd.ru")
    parser.add_argument("--origin", default="2000000", help="Origin station code.")
    parser.add_argument("--destination", default="2004000", help="Destination station code.")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD.")
    parser.add_argument("--return-date", default=None, help="Optional return date YYYY-MM-DD.")
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--service-provider", default="B2B_RZD")
    parser.add_argument("--car-issuing-type", default="Passenger")
    parser.add_argument("--get-trains-from-schedule", action="store_true", default=True)
    parser.add_argument("--no-get-trains-from-schedule", dest="get_trains_from_schedule", action="store_false")
    parser.add_argument("--get-by-local-time", action="store_true", default=True)
    parser.add_argument("--no-get-by-local-time", dest="get_by_local_time", action="store_false")
    parser.add_argument("--car-grouping", default="DontGroup")
    parser.add_argument("--special-places-demand", default="StandardPlacesAndForDisabledPersons")
    parser.add_argument("--has-places-for-large-family", action="store_true")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--x-client-id", default="22900")
    parser.add_argument("--x-ksid-bsid", default=None)
    parser.add_argument("--cookie", default=None)
    parser.add_argument("--auth-bearer", default=None)
    parser.add_argument("--try-variants", action="store_true", help="Try multiple param variants if no trains.")
    args = parser.parse_args()

    session = make_session(
        x_client_id=args.x_client_id,
        x_ksid_bsid=args.x_ksid_bsid,
        cookie=args.cookie,
        auth_bearer=args.auth_bearer,
        proxy=args.proxy,
    )

    def single(date_value: str, direction: str) -> tuple[bool, dict[str, Any]]:
        params = build_params(
            args.origin if direction == "forward" else args.destination,
            args.destination if direction == "forward" else args.origin,
            date_value,
            service_provider=args.service_provider,
            get_by_local_time=args.get_by_local_time,
            car_grouping=args.car_grouping,
            special_places_demand=args.special_places_demand,
            car_issuing_type=args.car_issuing_type,
            get_trains_from_schedule=args.get_trains_from_schedule,
            adults=args.adults,
            children=args.children,
            has_places_for_large_family=args.has_places_for_large_family,
        )
        ok, code, payload, url = run_search(session, params, args.timeout)
        print(f"\n=== {direction.upper()} {date_value} ===")
        print(f"HTTP: {code}")
        print(f"URL: {url}")
        if not ok:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return False, {}

        info = summarize(payload)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return True, payload

    all_ok = True
    ok_fwd, payload_fwd = single(args.date, "forward")
    all_ok = all_ok and ok_fwd

    payload_bwd: dict[str, Any] | None = None
    if args.return_date:
        ok_bwd, payload_bwd = single(args.return_date, "backward")
        all_ok = all_ok and ok_bwd

    if not all_ok:
        return 1

    no_trains = (
        isinstance(payload_fwd.get("Trains"), list) and len(payload_fwd.get("Trains", [])) == 0
        and (
            payload_bwd is None
            or (isinstance(payload_bwd.get("Trains"), list) and len(payload_bwd.get("Trains", [])) == 0)
        )
    )

    if args.try_variants and no_trains:
        print("\nNo trains in base query, trying variants...")
        variants = []
        for service_provider, get_by_local, from_schedule, issuing_type in product(
            [args.service_provider, None],
            [True, False],
            [True, False],
            [args.car_issuing_type, None],
        ):
            variants.append((service_provider, get_by_local, from_schedule, issuing_type))

        seen = set()
        for service_provider, get_by_local, from_schedule, issuing_type in variants:
            key = (service_provider, get_by_local, from_schedule, issuing_type)
            if key in seen:
                continue
            seen.add(key)

            params = build_params(
                args.origin,
                args.destination,
                args.date,
                service_provider=service_provider,
                get_by_local_time=get_by_local,
                car_grouping=args.car_grouping,
                special_places_demand=args.special_places_demand,
                car_issuing_type=issuing_type,
                get_trains_from_schedule=from_schedule,
                adults=args.adults,
                children=args.children,
                has_places_for_large_family=args.has_places_for_large_family,
            )
            ok, code, payload, _ = run_search(session, params, args.timeout)
            if not ok:
                print(f"variant failed: http={code} provider={service_provider} local={get_by_local} schedule={from_schedule} issuing={issuing_type}")
                continue
            trains = payload.get("Trains")
            count = len(trains) if isinstance(trains, list) else -1
            err = payload.get("errorInfo") if isinstance(payload, dict) else None
            err_code = err.get("Code") if isinstance(err, dict) else None
            print(
                f"variant provider={service_provider} local={get_by_local} "
                f"schedule={from_schedule} issuing={issuing_type} -> trains={count}, err_code={err_code}"
            )
            if count > 0:
                sample = trains[0]
                print("Found trains with variant. First train:")
                print(
                    json.dumps(
                        {
                            "TrainNumber": sample.get("TrainNumber"),
                            "DepartureDateTime": sample.get("DepartureDateTime"),
                            "ArrivalDateTime": sample.get("ArrivalDateTime"),
                            "OriginStationName": sample.get("OriginStationName"),
                            "DestinationStationName": sample.get("DestinationStationName"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
