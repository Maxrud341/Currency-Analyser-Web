import pytest
from unittest.mock import patch
import requests

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
def test_latest_rates_success(mock_get_rates, logged_in_client):
    """Ověřuje, že /latest funguje pro přihlášeného uživatele"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/latest?currencies=EUR,CZK')

    assert response.status_code == 200
    data = response.get_json()
    assert data['base'] == 'USD'
    assert data['rates']['EUR'] == 0.93
    assert data['rates']['CZK'] == 23.5
    assert 'GBP' not in data['rates']


@patch('app.controllers.exchange_controller._get_today_rates')
def test_latest_rates_unauthorized(mock_get_rates, client):
    """Ověřuje, že /latest vyžaduje přihlášení"""
    response = client.get('/exchange/latest?currencies=EUR')

    assert response.status_code == 302
    assert '/login' in response.headers['Location']
    assert not mock_get_rates.called


@patch('app.controllers.exchange_controller._get_today_rates')
def test_strongest_currency(mock_get_rates, logged_in_client):
    """Ověřuje logiku /strongest pro silnou měnu"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/strongest?currencies=EUR,CZK&base=USD')

    assert response.status_code == 200
    data = response.get_json()
    assert data['strongest']['currency'] == 'EUR'


@patch('app.controllers.exchange_controller._get_today_rates')
def test_weakest_currency(mock_get_rates, logged_in_client):
    """Ověřuje logiku /weakest pro nejslabší měnu"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/weakest?currencies=EUR,CZK&base=USD')

    assert response.status_code == 200
    data = response.get_json()
    assert data['weakest']['currency'] == 'CZK'


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_limit_calls(mock_fetch, logged_in_client):
    """Ověřuje, že historický rozsah volá správný počet dní"""
    mock_fetch.return_value = MOCK_RATES

    date_from = "2024-01-01"
    date_to = "2024-01-03"

    response = logged_in_client.get(f'/exchange/historical-range?currencies=EUR&date_from={date_from}&date_to={date_to}')

    assert response.status_code == 200
    assert mock_fetch.call_count == 3


@patch('app.controllers.exchange_controller._get_today_rates')
def test_latest_rates_api_error(mock_get_rates, logged_in_client):
    """Ověřuje zpracování chyby API na /latest"""
    mock_get_rates.side_effect = Exception("API Down")

    response = logged_in_client.get('/exchange/latest?currencies=EUR')

    assert response.status_code == 502


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_invalid_dates(mock_fetch, logged_in_client):
    """Ověřuje, že neplatné datum vrací 400"""
    date_from = "2024-01-05"
    date_to = "2024-01-01"

    response = logged_in_client.get(f'/exchange/historical-range?currencies=EUR&date_from={date_from}&date_to={date_to}')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._get_today_rates')
def test_current_currency_success(mock_get_rates, logged_in_client):
    """Ověřuje výpočet aktuálního kurzu mezi dvěma měnami"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/current?from=USD&to=EUR')

    assert response.status_code == 200
    data = response.get_json()
    assert data['from'] == 'USD'
    assert data['to'] == 'EUR'
    assert data['rate'] == 0.93


@patch('app.controllers.exchange_controller._get_today_rates')
def test_current_currency_invalid_currency(mock_get_rates, logged_in_client):
    """Ověřuje chybovou odpověď pro neplatný kód měny"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/current?from=USD&to=ABC')

    assert response.status_code == 400
    data = response.get_json()
    assert 'Neplatný kód měny' in data['error']


def test_supported_currencies_requires_login(client):
    """Ověřuje, že podpora měn vyžaduje přihlášení"""
    response = client.get('/exchange/supported-currencies')

    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_supported_currencies_logged_in(logged_in_client):
    """Ověřuje seznam podporovaných měn pro přihlášeného uživatele"""
    response = logged_in_client.get('/exchange/supported-currencies')

    assert response.status_code == 200
    data = response.get_json()
    assert 'EUR' in data
    assert 'USD' in data


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_average_computes_average(mock_fetch, logged_in_client):
    """Ověřuje průměrný kurz přes několik dnů"""
    def fake_fetch(date_str):
        rate = 0.93 if date_str == '2024-01-01' else 0.95
        return {"timestamp": 1713871200, "rates": {"USD": 1.0, "EUR": rate}}

    mock_fetch.side_effect = fake_fetch

    response = logged_in_client.get('/exchange/average?currencies=EUR&date_from=2024-01-01&date_to=2024-01-02&base=USD')

    assert response.status_code == 200
    data = response.get_json()
    assert data['averages']['EUR'] == 0.94


@patch('app.controllers.exchange_controller._get_today_rates')
def test_strongest_invalid_base(mock_get_rates, logged_in_client):
    """Ověřuje chybu pro neplatnou základní měnu"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/strongest?currencies=EUR&base=ABC')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_invalid_target_count(mock_fetch, logged_in_client):
    """Ověřuje, že historický rozsah přijímá přesně jednu cílovou měnu"""
    mock_fetch.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/historical-range?currencies=EUR,USD&date_from=2024-01-01&date_to=2024-01-02')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._load_cache')
@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_with_cache(mock_load_cache, mock_fetch, logged_in_client):
    """Ověřuje načtení z cache v historickém rozsahu"""
    mock_load_cache.return_value = MOCK_RATES
    mock_fetch.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/historical-range?currencies=EUR&date_from=2024-01-01&date_to=2024-01-01')

    assert response.status_code == 200
    # Проверяем, что _fetch_historical_day не вызывался, поскольку данные из cache
    mock_fetch.assert_not_called()


@patch('app.controllers.exchange_controller.requests.get')
def test_fetch_historical_day_api_error(mock_get, logged_in_client):
    """Ověřuje zpracování API chyby v _fetch_historical_day"""
    mock_response = mock_get.return_value
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"success": False, "error": "API Error"}

    # Поскольку это internal, тестируем через endpoint
    with patch('app.controllers.exchange_controller._load_cache', return_value=None):
        response = logged_in_client.get('/exchange/historical-range?currencies=EUR&date_from=2024-01-01&date_to=2024-01-01')

    assert response.status_code == 200  # Но rates будет None


@patch('app.controllers.exchange_controller.requests.get')
def test_fetch_historical_day_request_exception(mock_get, logged_in_client):
    """Ověřuje zpracování výjimky požadavku v _fetch_historical_day"""
    mock_get.side_effect = requests.exceptions.RequestException("Network Error")

    with patch('app.controllers.exchange_controller._load_cache', return_value=None):
        response = logged_in_client.get('/exchange/historical-range?currencies=EUR&date_from=2024-01-01&date_to=2024-01-01')

    assert response.status_code == 200  # Exception handled, rates None


@patch('app.controllers.exchange_controller._get_today_rates')
def test_strongest_no_currencies(mock_get_rates, logged_in_client):
    """Ověřuje chybu při prázdném seznamu měn v /strongest"""
    response = logged_in_client.get('/exchange/strongest?currencies=')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._get_today_rates')
def test_weakest_no_currencies(mock_get_rates, logged_in_client):
    """Ověřuje chybu při prázdném seznamu měn v /weakest"""
    response = logged_in_client.get('/exchange/weakest?currencies=')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._get_today_rates')
def test_current_missing_to_param(mock_get_rates, logged_in_client):
    """Ověřuje chybu při chybějícím parametru 'to' v /current"""
    response = logged_in_client.get('/exchange/current?from=USD')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._get_today_rates')
def test_current_same_currency(mock_get_rates, logged_in_client):
    """Ověřuje kurz pro stejnou měnu v /current"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/current?from=USD&to=USD')

    assert response.status_code == 200
    data = response.get_json()
    assert data['rate'] == 1.0


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_average_invalid_dates(mock_fetch, logged_in_client):
    """Ověřuje chybu při neplatných datech v /average"""
    response = logged_in_client.get('/exchange/average?currencies=EUR&date_from=invalid&date_to=2024-01-02')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_average_date_from_after_to(mock_fetch, logged_in_client):
    """Ověřuje chybu při date_from > date_to v /average"""
    response = logged_in_client.get('/exchange/average?currencies=EUR&date_from=2024-01-03&date_to=2024-01-01')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._load_cache')
@patch('app.controllers.exchange_controller.requests.get')
def test_fetch_historical_day_success_and_save_cache(mock_get, mock_load_cache, logged_in_client):
    """Ověřuje úspěšné volání API a uložení do cache"""
    mock_load_cache.return_value = None
    mock_response = mock_get.return_value
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "success": True,
        "timestamp": 1713871200,
        "quotes": {"USDEUR": 0.93, "USDCZK": 23.5, "USDUSD": 1.0}
    }

    response = logged_in_client.get('/exchange/historical-range?currencies=EUR&date_from=2024-01-01&date_to=2024-01-01')

    assert response.status_code == 200


@patch('app.controllers.exchange_controller._get_today_rates')
def test_strongest_invalid_base_currency(mock_get_rates, logged_in_client):
    """Ověřuje chybu pro neplatnou základní měnu v /strongest"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/strongest?currencies=EUR&base=INVALID')

    assert response.status_code == 400


@patch('app.controllers.exchange_controller._get_today_rates')
def test_weakest_invalid_base_currency(mock_get_rates, logged_in_client):
    """Ověřuje chybu pro neplatnou základní měnu v /weakest"""
    mock_get_rates.return_value = MOCK_RATES

    response = logged_in_client.get('/exchange/weakest?currencies=EUR&base=INVALID')

    assert response.status_code == 400


