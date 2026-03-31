"""
Integration tests for the RZD API Python library.
Tests run against the live pass.rzd.ru API.
"""

import json
from datetime import datetime, timedelta

import pytest

from rzd_api import Api


@pytest.fixture(scope="module")
def api():
    return Api()


@pytest.fixture(scope="module")
def dates():
    tomorrow = datetime.now() + timedelta(days=1)
    in_6_days = datetime.now() + timedelta(days=6)
    return {
        'dt0': tomorrow.strftime('%d.%m.%Y'),
        'dt1': in_6_days.strftime('%d.%m.%Y'),
    }


# Station codes: Saint Petersburg (2004000) -> Moscow (2000000)
SPB = '2004000'
MSK = '2000000'


def test_train_routes(api, dates):
    params = {
        'dir': 0,
        'tfl': 3,
        'checkSeats': 1,
        'code0': SPB,
        'code1': MSK,
        'dt0': dates['dt0'],
    }
    result = api.train_routes(params)
    trains = json.loads(result)

    assert isinstance(trains, list)
    assert len(trains) > 0
    assert 'route0' in trains[0]
    assert trains[0]['route0'] == 'С-ПЕТЕР-ГЛ'


def test_train_routes_return(api, dates):
    params = {
        'dir': 1,
        'tfl': 3,
        'checkSeats': 1,
        'code0': SPB,
        'code1': MSK,
        'dt0': dates['dt0'],
        'dt1': dates['dt1'],
    }
    result = api.train_routes_return(params)
    data = json.loads(result)

    assert isinstance(data, dict)
    assert 'forward' in data
    assert 'back' in data
    assert isinstance(data['forward'], list)
    assert isinstance(data['back'], list)
    assert data['forward'][0]['route0'] == 'С-ПЕТЕР-ГЛ'


def test_train_carriages(api, dates):
    route_params = {
        'dir': 0,
        'tfl': 3,
        'checkSeats': 1,
        'code0': SPB,
        'code1': MSK,
        'dt0': dates['dt0'],
    }
    routes = json.loads(api.train_routes(route_params))

    if routes:
        first = routes[0]
        carriage_params = {
            'dir': 0,
            'code0': SPB,
            'code1': MSK,
            'dt0': first['date0'],
            'time0': first['time0'],
            'tnum0': first['number'],
        }
        result = api.train_carriages(carriage_params)
        data = json.loads(result)

        assert isinstance(data, dict)
        assert 'cars' in data
        assert data['cars'] is not None
        assert len(data['cars']) > 0
        assert 'cnumber' in data['cars'][0]


def test_train_station_list(api, dates):
    params = {
        'trainNumber': '054Г',
        'depDate': dates['dt0'],
    }
    result = api.train_station_list(params)
    data = json.loads(result)

    assert isinstance(data, dict)
    assert 'train' in data
    assert 'routes' in data
    assert data['train']['number'] == '054Г'


def test_station_code(api):
    params = {
        'stationNamePart': 'ЧЕБ',
        'compactMode': 'y',
    }
    result = api.station_code(params)
    stations = json.loads(result)

    assert isinstance(stations, list)
    city_names = [s['station'] for s in stations]
    assert 'ЧЕБОКСАРЫ' in city_names
