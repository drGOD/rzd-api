from datetime import date, datetime

import pytest

from rzd_api import RzdClient, RzdException


class FakeApi:
    def __init__(self):
        self.calls = []

    def train_routes_data(self, params):
        self.calls.append(('train_routes_data', params))
        return [{'TrainNumber': '001A'}]

    def train_routes_return_data(self, params):
        self.calls.append(('train_routes_return_data', params))
        return {'forward': [{'TrainNumber': '001A'}], 'back': [{'TrainNumber': '002A'}]}

    def train_carriages_data(self, params):
        self.calls.append(('train_carriages_data', params))
        return {'cars': [{'CarNumber': '01'}]}

    def train_station_list_data(self, params):
        self.calls.append(('train_station_list_data', params))
        return {'train': {'TrainNumber': params['id']}, 'routes': []}

    def station_code_data(self, params):
        self.calls.append(('station_code_data', params))
        query = params['stationNamePart'].upper()
        stations = {
            'МОСКВА': [{'station': 'МОСКВА', 'code': '2000000'}],
            'САНКТ-ПЕТЕРБУРГ': [{'station': 'САНКТ-ПЕТЕРБУРГ', 'code': '2004000'}],
            'ПЕТЕР': [{'station': 'САНКТ-ПЕТЕРБУРГ', 'code': '2004000'}],
        }
        return stations.get(query, [])


@pytest.fixture()
def client():
    return RzdClient(api=FakeApi())


def test_search_tickets_by_station_names(client):
    result = client.search_tickets('Санкт-Петербург', 'Москва', date(2026, 4, 3))

    assert result == [{'TrainNumber': '001A'}]
    method, params = client.api.calls[-1]
    assert method == 'train_routes_data'
    assert params == {
        'origin': '2004000',
        'destination': '2000000',
        'departureDate': '2026-04-03T00:00:00',
        'adultPassengersQuantity': 1,
        'childrenPassengersQuantity': 0,
    }


def test_search_round_trip_with_codes_and_datetime(client):
    result = client.search_tickets(
        '2004000',
        '2000000',
        datetime(2026, 4, 3, 10, 30),
        return_date='07.04.2026',
        only_with_seats=False,
        include_transfers=True,
        transport_type='trains',
    )

    assert result['back'][0]['TrainNumber'] == '002A'
    method, params = client.api.calls[-1]
    assert method == 'train_routes_return_data'
    assert params == {
        'origin': '2004000',
        'destination': '2000000',
        'departureDate': '2026-04-03T10:30:00',
        'returnDate': '2026-04-07T00:00:00',
        'adultPassengersQuantity': 1,
        'childrenPassengersQuantity': 0,
    }


def test_get_carriages_uses_resolved_codes(client):
    result = client.get_carriages('Петер', 'Москва', '03.04.2026', '22:30', '001A')

    assert result['cars'][0]['CarNumber'] == '01'
    method, params = client.api.calls[-1]
    assert method == 'train_carriages_data'
    assert params['OriginCode'] == '2004000'
    assert params['DestinationCode'] == '2000000'
    assert params['DepartureDate'] == '2026-04-03T22:30:00'
    assert params['TrainNumber'] == '001A'


def test_get_route_stations_formats_date(client):
    result = client.get_route_stations('054Г')

    assert result['train']['TrainNumber'] == '054Г'
    method, params = client.api.calls[-1]
    assert method == 'train_station_list_data'
    assert params['id'] == '054Г'


def test_resolve_station_code_prefers_exact_match(client):
    assert client.resolve_station_code('Москва') == '2000000'


def test_resolve_station_code_raises_for_unknown_station(client):
    with pytest.raises(RzdException, match='Station not found'):
        client.resolve_station_code('Неизвестная станция')


def test_search_tickets_rejects_unknown_transport_type(client):
    with pytest.raises(ValueError, match='Unsupported transport_type'):
        client.search_tickets('Москва', 'Санкт-Петербург', '03.04.2026', transport_type='plane')
