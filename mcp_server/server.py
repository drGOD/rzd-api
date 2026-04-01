"""
MCP Server for RZD (Russian Railways) API.

Exposes rzd_api as MCP tools so any MCP-compatible client (Claude, etc.)
can search train routes, carriages, and station codes.

Transport is configured via environment variables:
  MCP_TRANSPORT  — stdio (default) | sse | streamable-http
  MCP_HOST       — bind host for HTTP transports (default: 0.0.0.0)
  MCP_PORT       — bind port for HTTP transports (default: 8000)
"""

import os
import sys

from rzd_api import Api

mcp = None

_api: Api | None = None


def get_api() -> Api:
    global _api
    if _api is None:
        _api = Api()
    return _api


def train_routes(
    origin: str,
    destination: str,
    departure_date: str,
    adult_passengers_quantity: int = 1,
    children_passengers_quantity: int = 0,
) -> str:
    """Get one-way train routes with available seats and prices.

    Args:
        origin: Origin station code (e.g. '2004000' for Saint Petersburg).
        destination: Destination station code (e.g. '2000000' for Moscow).
        departure_date: Departure date in format YYYY-MM-DD or ISO datetime.
        adult_passengers_quantity: Number of adults.
        children_passengers_quantity: Number of children.

    Returns:
        JSON array of train objects with seats and pricing info.
    """
    params = {
        'origin': origin,
        'destination': destination,
        'departureDate': departure_date,
        'adultPassengersQuantity': adult_passengers_quantity,
        'childrenPassengersQuantity': children_passengers_quantity,
    }
    return get_api().train_routes(params)


def train_routes_return(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    adult_passengers_quantity: int = 1,
    children_passengers_quantity: int = 0,
) -> str:
    """Get round-trip train routes (forward + back legs).

    Args:
        origin: Origin station code (e.g. '2004000' for Saint Petersburg).
        destination: Destination station code (e.g. '2000000' for Moscow).
        departure_date: Departure date in format YYYY-MM-DD or ISO datetime.
        return_date: Return date in format YYYY-MM-DD or ISO datetime.
        adult_passengers_quantity: Number of adults.
        children_passengers_quantity: Number of children.

    Returns:
        JSON object with 'forward' and 'back' arrays of train objects.
    """
    params = {
        'origin': origin,
        'destination': destination,
        'departureDate': departure_date,
        'returnDate': return_date,
        'adultPassengersQuantity': adult_passengers_quantity,
        'childrenPassengersQuantity': children_passengers_quantity,
    }
    return get_api().train_routes_return(params)


def train_carriages(
    origin_code: str,
    destination_code: str,
    departure_datetime: str,
    train_number: str,
    car_number: str = '01',
    provider: str = 'P1',
) -> str:
    """Get detailed carriage and seat information for a specific train.

    Args:
        origin_code: Origin station code.
        destination_code: Destination station code.
        departure_datetime: Departure date-time in ISO format.
        train_number: Train number (e.g. '054Г').
        car_number: Car number (e.g. '01').
        provider: Provider code, default 'P1'.

    Returns:
        JSON object with 'cars', 'functionBlocks', 'schemes', and 'companies'.
    """
    params = {
        'OriginCode': origin_code,
        'DestinationCode': destination_code,
        'DepartureDate': departure_datetime,
        'TrainNumber': train_number,
        'CarNumber': car_number,
        'Provider': provider,
    }
    return get_api().train_carriages(params)


def train_station_list(
    object_id: str,
) -> str:
    """Get all stations on a train's route with arrival/departure times and distances.

    Args:
        object_id: Object id for /getobject endpoint.

    Returns:
        JSON object with 'train' info and 'routes' array of station objects.
    """
    params = {
        'id': object_id,
    }
    return get_api().train_station_list(params)


def station_code(
    station_name_part: str,
    transport_type: str = 'rail,suburban',
    group_results: bool = True,
) -> str:
    """Search for station codes by partial station name (in Russian).

    Args:
        station_name_part: Part of the station name (min 2 characters, e.g. 'ЧЕБ').
        transport_type: Transport types filter, default 'rail,suburban'.
        group_results: Grouping behavior, default True.

    Returns:
        JSON array of objects with 'station' name and 'code' fields.
    """
    params = {
        'stationNamePart': station_name_part,
        'transportType': transport_type,
        'groupResults': group_results,
    }
    return get_api().station_code(params)


def create_mcp_app():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is not installed. Install it with: pip install 'rzd-api[mcp]'"
        ) from exc

    app = FastMCP("RZD API")
    app.tool()(train_routes)
    app.tool()(train_routes_return)
    app.tool()(train_carriages)
    app.tool()(train_station_list)
    app.tool()(station_code)
    return app


def main() -> None:
    try:
        app = create_mcp_app()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    transport = os.getenv('MCP_TRANSPORT', 'stdio')
    if transport in ('sse', 'streamable-http'):
        host = os.getenv('MCP_HOST', '0.0.0.0')
        port = int(os.getenv('MCP_PORT', '8000'))
        app.run(transport=transport, host=host, port=port)
    else:
        app.run(transport='stdio')


if __name__ == '__main__':
    main()
