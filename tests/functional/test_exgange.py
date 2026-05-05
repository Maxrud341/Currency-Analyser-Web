import pytest
from unittest.mock import patch

MOCK_RATES = {
    "timestamp": 1713871200,
    "rates": {
        "USD": 1.0,
        "EUR": 0.93,
        "CZK": 23.5,
        "GBP": 0.80
    }
}


@patch('app.controllers.exchange_controller._get_today_rates')
def test_latest_rates_success(mock_get_rates, client):
    """Test /latest: ověřuje, že endpoint správně vrací data"""
    mock_get_rates.return_value = MOCK_RATES

    response = client.get('/exchange/latest?currencies=EUR,CZK')

    assert response.status_code == 200
    data = response.get_json()
    assert data['base'] == 'USD'
    assert data['rates']['EUR'] == 0.93
    assert data['rates']['CZK'] == 23.5
    assert 'GBP' not in data['rates']


@patch('app.controllers.exchange_controller._get_today_rates')
def test_strongest_currency(mock_get_rates, client):
    """Test /strongest: ověřuje logiku hledání nejsilnější měny"""
    mock_get_rates.return_value = MOCK_RATES

    response = client.get('/exchange/strongest?currencies=EUR,CZK&base=USD')

    assert response.status_code == 200
    data = response.get_json()
    assert data['strongest']['currency'] == 'EUR'

@patch('app.controllers.exchange_controller._get_today_rates')
def test_weakest_currency(mock_get_rates, client):
    """Test /weakest: ověřuje logiku hledání nejslabší měny"""
    mock_get_rates.return_value = MOCK_RATES

    response = client.get('/exchange/weakest?currencies=EUR,CZK&base=USD')

    assert response.status_code == 200
    data = response.get_json()
    assert data['weakest']['currency'] == 'CZK'

@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_limit_calls(mock_fetch, client):
    """Ověřuje, že rozsah dat volá funkci správný početkrát"""
    mock_fetch.return_value = MOCK_RATES

    date_from = "2024-01-01"
    date_to = "2024-01-03"

    response = client.get(f'/exchange/historical-range?currencies=EUR&date_from={date_from}&date_to={date_to}')

    assert response.status_code == 200
    assert mock_fetch.call_count == 3


@patch('app.controllers.exchange_controller._get_today_rates')
def test_latest_rates_api_error(mock_get_rates, client):
    """Test /latest: simuluje výpadek externího API a ověřuje zpracování chyby"""
    mock_get_rates.side_effect = Exception("API Down")

    response = client.get('/exchange/latest?currencies=EUR')

    assert response.status_code == 502


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_invalid_dates(mock_fetch, client):
    """Ověřuje ošetření chyby, když je počáteční datum větší než koncové"""
    date_from = "2024-01-05"
    date_to = "2024-01-01"

    response = client.get(f'/exchange/historical-range?currencies=EUR&date_from={date_from}&date_to={date_to}')

    assert response.status_code == 400


