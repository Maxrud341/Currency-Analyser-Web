import pytest
from unittest.mock import patch

# Пример данных, которые как будто вернул твой кеш или API
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
    """Тест /latest: проверяем, что эндпоинт правильно отдает данные"""
    # Настраиваем подмену: функция всегда возвращает наш MOCK_RATES
    mock_get_rates.return_value = MOCK_RATES

    response = client.get('/exchange/latest?currencies=EUR,CZK')

    assert response.status_code == 200
    data = response.get_json()
    assert data['base'] == 'USD'
    assert data['rates']['EUR'] == 0.93
    assert data['rates']['CZK'] == 23.5
    assert 'GBP' not in data['rates']  # Мы просили только EUR и CZK


@patch('app.controllers.exchange_controller._get_today_rates')
def test_strongest_currency(mock_get_rates, client):
    """Тест /strongest: проверяем логику поиска самой сильной валюты"""
    mock_get_rates.return_value = MOCK_RATES

    # Сравним EUR и CZK относительно USD
    # Напомню: в твоей логике 1/rate. Чем меньше rate, тем сильнее валюта.
    response = client.get('/exchange/strongest?currencies=EUR,CZK&base=USD')

    assert response.status_code == 200
    data = response.get_json()
    # EUR (0.93) сильнее чем CZK (23.5)
    assert data['strongest']['currency'] == 'EUR'


@patch('app.controllers.exchange_controller._fetch_historical_day')
def test_historical_range_limit_calls(mock_fetch, client):
    """Проверка, что диапазон дат вызывает функцию нужное количество раз"""
    mock_fetch.return_value = MOCK_RATES

    date_from = "2024-01-01"
    date_to = "2024-01-03"  # 3 дня

    response = client.get(f'/exchange/historical-range?currencies=EUR&date_from={date_from}&date_to={date_to}')

    assert response.status_code == 200
    # Проверяем, что функция _fetch_historical_day была вызвана ровно 3 раза
    assert mock_fetch.call_count == 3