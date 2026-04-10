# app/controllers/exchange_controller.py
import json
import os
import requests
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from dotenv import load_dotenv

load_dotenv()

exchange_bp = Blueprint('exchange', __name__, url_prefix='/exchange')

API_KEY = os.environ.get('EXCHANGERATE_HOST_KEY')
BASE_URL = 'https://api.exchangerate.host'
BASE_CURRENCY = 'USD'
CACHE_DIR = 'cache'
CACHE_MAX_AGE_DAYS = 7

os.makedirs(CACHE_DIR, exist_ok=True)


# ─── кеш хелперы ────────────────────────────────────────────────────────────

def _cache_path(key: str) -> str:
    safe = key.replace('/', '_').replace('?', '_').replace('&', '_')
    return os.path.join(CACHE_DIR, f'{safe}.json')


def _load_cache(key: str):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            cached = json.load(f)
        saved_at = datetime.fromisoformat(cached['_cached_at'])
        if datetime.now() - saved_at > timedelta(days=CACHE_MAX_AGE_DAYS):
            return None
        return cached['data']
    except Exception:
        return None


def _save_cache(key: str, data: dict):
    path = _cache_path(key)
    try:
        with open(path, 'w') as f:
            json.dump({'_cached_at': datetime.now().isoformat(), 'data': data}, f)
    except Exception as e:
        _log_error(f'Cache save error: {e}')


# ─── логирование ошибок ──────────────────────────────────────────────────────

def _log_error(message: str):
    os.makedirs('logs', exist_ok=True)
    with open('logs/errors.log', 'a') as f:
        f.write(f'[{datetime.now().isoformat()}] {message}\n')


# ─── запрос к API ────────────────────────────────────────────────────────────

def _fetch(endpoint: str, params: dict) -> dict | None:
    cache_key = endpoint + '_' + '_'.join(f'{k}{v}' for k, v in sorted(params.items()))
    cached = _load_cache(cache_key)
    if cached:
        return cached

    params['access_key'] = API_KEY
    try:
        response = requests.get(f'{BASE_URL}/{endpoint}', params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('success', True):
            raise ValueError(data.get('error', {}).get('info', 'API error'))
        _save_cache(cache_key, data)
        return data
    except Exception as e:
        _log_error(f'API error [{endpoint}]: {e}')
        return None


# ─── эндпоинты ───────────────────────────────────────────────────────────────

# GET /exchange/latest?currencies=EUR,CZK,GBP
@exchange_bp.route('/latest')
def latest():
    """Актуальные курсы выбранных валют относительно USD"""
    currencies = request.args.get('currencies', '')

    data = _fetch('live', {
        'source': BASE_CURRENCY,
        'currencies': currencies
    })

    if not data:
        return jsonify({'error': 'Не удалось получить данные, смотрите logs/errors.log'}), 502

    quotes = data.get('quotes', {})
    # убираем префикс "USD" из ключей: USDEUR → EUR
    rates = {k[len(BASE_CURRENCY):]: v for k, v in quotes.items()}

    return jsonify({
        'base': BASE_CURRENCY,
        'timestamp': data.get('timestamp'),
        'rates': rates
    })


# GET /exchange/strongest?currencies=EUR,CZK,GBP,JPY
@exchange_bp.route('/strongest')
def strongest():
    """Самая сильная валюта (наибольшее значение курса) среди выбранных"""
    currencies = request.args.get('currencies', '')
    if not currencies:
        return jsonify({'error': 'Параметр currencies обязателен'}), 400

    data = _fetch('live', {
        'source': BASE_CURRENCY,
        'currencies': currencies
    })

    if not data:
        return jsonify({'error': 'Не удалось получить данные'}), 502

    rates = {k[len(BASE_CURRENCY):]: v for k, v in data.get('quotes', {}).items()}
    if not rates:
        return jsonify({'error': 'Нет данных по выбранным валютам'}), 404

    strongest_code = max(rates, key=lambda c: rates[c])

    return jsonify({
        'base': BASE_CURRENCY,
        'strongest': {
            'currency': strongest_code,
            'rate': rates[strongest_code]
        },
        'all_rates': rates
    })


# GET /exchange/weakest?currencies=EUR,CZK,GBP,JPY
@exchange_bp.route('/weakest')
def weakest():
    """Самая слабая валюта (наименьшее значение курса) среди выбранных"""
    currencies = request.args.get('currencies', '')
    if not currencies:
        return jsonify({'error': 'Параметр currencies обязателен'}), 400

    data = _fetch('live', {
        'source': BASE_CURRENCY,
        'currencies': currencies
    })

    if not data:
        return jsonify({'error': 'Не удалось получить данные'}), 502

    rates = {k[len(BASE_CURRENCY):]: v for k, v in data.get('quotes', {}).items()}
    if not rates:
        return jsonify({'error': 'Нет данных по выбранным валютам'}), 404

    weakest_code = min(rates, key=lambda c: rates[c])

    return jsonify({
        'base': BASE_CURRENCY,
        'weakest': {
            'currency': weakest_code,
            'rate': rates[weakest_code]
        },
        'all_rates': rates
    })


# GET /exchange/average?currencies=EUR,CZK&date_from=2024-01-01&date_to=2024-01-31
@exchange_bp.route('/average')
def average():
    """Среднеарифметический курс валют за период"""
    currencies = request.args.get('currencies', '')
    date_from  = request.args.get('date_from')
    date_to    = request.args.get('date_to')

    if not all([currencies, date_from, date_to]):
        return jsonify({'error': 'Нужны параметры: currencies, date_from, date_to'}), 400

    try:
        start = datetime.strptime(date_from, '%Y-%m-%d')
        end   = datetime.strptime(date_to,   '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Формат дат: YYYY-MM-DD'}), 400

    if start > end:
        return jsonify({'error': 'date_from не может быть позже date_to'}), 400

    # собираем курсы по каждому дню
    sums   = {}
    counts = {}
    current = start

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        data = _fetch('historical', {
            'date': date_str,
            'source': BASE_CURRENCY,
            'currencies': currencies
        })

        if data:
            quotes = data.get('quotes', {})
            for key, value in quotes.items():
                code = key[len(BASE_CURRENCY):]
                sums[code]   = sums.get(code, 0) + value
                counts[code] = counts.get(code, 0) + 1

        current += timedelta(days=1)

    if not sums:
        return jsonify({'error': 'Нет данных за указанный период'}), 404

    averages = {code: round(sums[code] / counts[code], 6) for code in sums}

    return jsonify({
        'base': BASE_CURRENCY,
        'date_from': date_from,
        'date_to': date_to,
        'days_counted': counts,
        'averages': averages
    })