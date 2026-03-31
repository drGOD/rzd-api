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

from mcp.server.fastmcp import FastMCP

from rzd_api import Api, Config

mcp = FastMCP("RZD API")

_api: Api | None = None


def get_api() -> Api:
    global _api
    if _api is None:
        _api = Api()
    return _api


@mcp.tool()
def train_routes(
    code0: str,
    code1: str,
    dt0: str,
    dir: int = 0,
    tfl: int = 3,
    check_seats: int = 1,
    md: int = 0,
) -> str:
    """Get one-way train routes with available seats and prices.

    Args:
        code0: Origin station code (e.g. '2004000' for Saint Petersburg).
        code1: Destination station code (e.g. '2000000' for Moscow).
        dt0: Departure date in format dd.mm.yyyy.
        dir: Direction — 0 one-way (default).
        tfl: Train type: 1 = trains only, 2 = electric trains only, 3 = both (default).
        check_seats: 1 = only trains with seats (default), 0 = all trains.
        md: 0 = direct routes only (default), 1 = with transfers.

    Returns:
        JSON array of train objects with seats and pricing info.
    """
    params = {
        'code0': code0,
        'code1': code1,
        'dt0': dt0,
        'dir': dir,
        'tfl': tfl,
        'checkSeats': check_seats,
        'md': md,
    }
    return get_api().train_routes(params)


@mcp.tool()
def train_routes_return(
    code0: str,
    code1: str,
    dt0: str,
    dt1: str,
    tfl: int = 3,
    check_seats: int = 1,
) -> str:
    """Get round-trip train routes (forward + back legs).

    Args:
        code0: Origin station code (e.g. '2004000' for Saint Petersburg).
        code1: Destination station code (e.g. '2000000' for Moscow).
        dt0: Departure date in format dd.mm.yyyy.
        dt1: Return date in format dd.mm.yyyy.
        tfl: Train type: 1 = trains only, 2 = electric trains only, 3 = both (default).
        check_seats: 1 = only trains with seats (default), 0 = all trains.

    Returns:
        JSON object with 'forward' and 'back' arrays of train objects.
    """
    params = {
        'code0': code0,
        'code1': code1,
        'dt0': dt0,
        'dt1': dt1,
        'dir': 1,
        'tfl': tfl,
        'checkSeats': check_seats,
    }
    return get_api().train_routes_return(params)


@mcp.tool()
def train_carriages(
    code0: str,
    code1: str,
    dt0: str,
    time0: str,
    tnum0: str,
    dir: int = 0,
) -> str:
    """Get detailed carriage and seat information for a specific train.

    Args:
        code0: Origin station code.
        code1: Destination station code.
        dt0: Departure date in format dd.mm.yyyy.
        time0: Departure time in format HH:MM.
        tnum0: Train number (e.g. '054Г').
        dir: Direction — 0 one-way (default).

    Returns:
        JSON object with 'cars', 'functionBlocks', 'schemes', and 'companies'.
    """
    params = {
        'code0': code0,
        'code1': code1,
        'dt0': dt0,
        'time0': time0,
        'tnum0': tnum0,
        'dir': dir,
    }
    return get_api().train_carriages(params)


@mcp.tool()
def train_station_list(
    train_number: str,
    dep_date: str,
) -> str:
    """Get all stations on a train's route with arrival/departure times and distances.

    Args:
        train_number: Train number (e.g. '054Г').
        dep_date: Departure date in format dd.mm.yyyy.

    Returns:
        JSON object with 'train' info and 'routes' array of station objects.
    """
    params = {
        'trainNumber': train_number,
        'depDate': dep_date,
    }
    return get_api().train_station_list(params)


@mcp.tool()
def station_code(
    station_name_part: str,
    compact_mode: str = 'y',
) -> str:
    """Search for station codes by partial station name (in Russian).

    Args:
        station_name_part: Part of the station name (min 2 characters, e.g. 'ЧЕБ').
        compact_mode: Response format, default 'y'.

    Returns:
        JSON array of objects with 'station' name and 'code' fields.
    """
    params = {
        'stationNamePart': station_name_part,
        'compactMode': compact_mode,
    }
    return get_api().station_code(params)


def main() -> None:
    transport = os.getenv('MCP_TRANSPORT', 'stdio')
    if transport in ('sse', 'streamable-http'):
        host = os.getenv('MCP_HOST', '0.0.0.0')
        port = int(os.getenv('MCP_PORT', '8000'))
        mcp.run(transport=transport, host=host, port=port)
    else:
        mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
