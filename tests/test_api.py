import json

from rzd_api import Api


class FakeQuery:
    def __init__(self):
        self.calls = []

    def get(self, path, params=None, method='POST', json_body=None):
        self.calls.append({
            'path': path,
            'params': params or {},
            'method': method,
            'json_body': json_body,
        })

        if path.endswith('/railway-service/prices/train-pricing'):
            return {'data': {'trains': [{'number': '001А'}]}}
        if path.endswith('/suggests'):
            return [{'n': 'МОСКВА', 'c': '2000000'}]
        if path.endswith('/railway/car/place/prices'):
            return {'cars': [{'cnumber': '03'}]}
        if path.endswith('/getobject'):
            return {'trainInfo': {'number': '054Г'}, 'routes': []}
        return {}


def make_api():
    api = Api()
    api.query = FakeQuery()
    return api


def test_train_routes_uses_new_endpoint_and_returns_json():
    api = make_api()

    result = json.loads(api.train_routes({
        'code0': '2004000',
        'code1': '2000000',
        'dt0': '03.04.2026',
    }))

    assert result[0]['number'] == '001А'
    last = api.query.calls[-1]
    assert last['method'] == 'GET'
    assert last['path'].endswith('/api/v1/railway-service/prices/train-pricing')
    assert last['params']['origin'] == '2004000'
    assert last['params']['destination'] == '2000000'
    assert last['params']['departureDate'] == '2026-04-03T00:00:00'


def test_train_routes_return_calls_pricing_twice():
    api = make_api()
    result = json.loads(api.train_routes_return({
        'code0': '2004000',
        'code1': '2000000',
        'dt0': '03.04.2026',
        'dt1': '07.04.2026',
    }))

    assert 'forward' in result
    assert 'back' in result
    pricing_calls = [
        call for call in api.query.calls
        if call['path'].endswith('/api/v1/railway-service/prices/train-pricing')
    ]
    assert len(pricing_calls) == 2


def test_train_carriages_uses_new_post_endpoint():
    api = make_api()
    result = json.loads(api.train_carriages({
        'code0': '2004000',
        'code1': '2000000',
        'dt0': '03.04.2026',
        'time0': '22:30',
        'tnum0': '751А',
        'CarNumber': '03',
    }))

    assert result['cars'][0]['cnumber'] == '03'
    last = api.query.calls[-1]
    assert last['method'] == 'POST'
    assert last['path'].endswith('/api/v1/railway/car/place/prices')
    assert last['json_body']['OriginCode'] == '2004000'
    assert last['json_body']['DestinationCode'] == '2000000'
    assert last['json_body']['TrainNumber'] == '751А'
    assert last['json_body']['DepartureDate'] == '2026-04-03T22:30:00'


def test_train_station_list_uses_getobject():
    api = make_api()
    result = json.loads(api.train_station_list({
        'trainNumber': '054Г',
        'depDate': '03.04.2026',
    }))

    assert result['train']['number'] == '054Г'
    last = api.query.calls[-1]
    assert last['method'] == 'GET'
    assert last['path'].endswith('/api/v1/getobject')
    assert last['params']['id'] == '054Г'


def test_station_code_uses_suggests():
    api = make_api()
    result = json.loads(api.station_code({
        'stationNamePart': 'МОСК',
    }))

    assert result == [{'station': 'МОСКВА', 'code': '2000000'}]
    last = api.query.calls[-1]
    assert last['method'] == 'GET'
    assert last['path'].endswith('/api/v1/suggests')
    assert last['params']['Query'] == 'МОСК'
