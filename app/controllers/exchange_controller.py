# app/controllers/exchange_controller.py
import json
import os
import requests
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from dotenv import load_dotenv
from app.logger import get_logger

load_dotenv()

logger = get_logger('exchange')

exchange_bp = Blueprint('exchange', __name__, url_prefix='/exchange')

API_KEY = os.environ.get('EXCHANGERATE_HOST_KEY')
BASE_URL = 'https://api.exchangerate.host'
BASE_CURRENCY = 'USD'
CACHE_DIR = 'cache'
CACHE_MAX_AGE_DAYS = 7

os.makedirs(CACHE_DIR, exist_ok=True)


# ─── cache helpers ────────────────────────────────────────────────────────────

def _cache_path(key: str) -> str:
    safe = key.replace('/', '_').replace('?', '_').replace('&', '_')
    return os.path.join(CACHE_DIR, f'{safe}.json')


def _load_cache(key: str):
    path = _cache_path(key)
    if not os.path.exists(path):
        logger.debug('Cache miss: %s', key)
        return None
    try:
        with open(path, 'r') as f:
            cached = json.load(f)
        saved_at = datetime.fromisoformat(cached['_cached_at'])
        if datetime.now() - saved_at > timedelta(days=CACHE_MAX_AGE_DAYS):
            logger.debug('Cache expired: %s', key)
            return None
        logger.debug('Cache hit: %s', key)
        return cached['data']
    except Exception as e:
        logger.error('Cache read error [%s]: %s', key, e)
        return None


def _save_cache(key: str, data: dict):
    path = _cache_path(key)
    try:
        with open(path, 'w') as f:
            json.dump({'_cached_at': datetime.now().isoformat(), 'data': data}, f)
        logger.debug('Cache saved: %s', key)
    except Exception as e:
        logger.error('Cache save error [%s]: %s', key, e)


# ─── API request ──────────────────────────────────────────────────────────────

def _fetch(endpoint: str, params: dict) -> dict | None:
    cache_key = endpoint + '_' + '_'.join(f'{k}{v}' for k, v in sorted(params.items()))
    cached = _load_cache(cache_key)
    if cached:
        return cached

    params['access_key'] = API_KEY
    try:
        safe_params = {k: v for k, v in params.items() if k != 'access_key'}
        logger.info('API request: %s | params: %s', endpoint, safe_params)
        response = requests.get(f'{BASE_URL}/{endpoint}', params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('success', True):
            raise ValueError(data.get('error', {}).get('info', 'API error'))
        logger.info('API success: %s', endpoint)
        _save_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error('API error [%s]: %s', endpoint, e)
        return None


# ─── endpoints ────────────────────────────────────────────────────────────────

# GET /exchange/latest?currencies=EUR,CZK,GBP
@exchange_bp.route('/latest')
def latest():
    currencies = request.args.get('currencies', '')
    logger.info('GET /latest | currencies: %s', currencies or 'all')

    data = _fetch('live', {
        'source': BASE_CURRENCY,
        **(({'currencies': currencies}) if currencies else {})
    })

    if not data:
        logger.error('GET /latest failed | currencies: %s', currencies or 'all')
        return jsonify({'error': 'Failed to fetch data, check logs/app.log'}), 502

    quotes = data.get('quotes', {})
    rates = {k[len(BASE_CURRENCY):]: v for k, v in quotes.items()}
    logger.info('GET /latest success | returned %d currencies', len(rates))

    return jsonify({
        'base': BASE_CURRENCY,
        'timestamp': data.get('timestamp'),
        'rates': rates
    })


# GET /exchange/strongest?currencies=EUR,CZK,GBP,JPY
@exchange_bp.route('/strongest')
def strongest():
    currencies = request.args.get('currencies', '')
    logger.info('GET /strongest | currencies: %s', currencies)

    if not currencies:
        logger.warning('GET /strongest | missing required parameter: currencies')
        return jsonify({'error': 'Parameter currencies is required'}), 400

    data = _fetch('live', {
        'source': BASE_CURRENCY,
        'currencies': currencies
    })

    if not data:
        logger.error('GET /strongest failed | currencies: %s', currencies)
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = {k[len(BASE_CURRENCY):]: v for k, v in data.get('quotes', {}).items()}

    if not rates:
        logger.warning('GET /strongest | no data for currencies: %s', currencies)
        return jsonify({'error': 'No data for selected currencies'}), 404

    strongest_code = max(rates, key=lambda c: rates[c])
    logger.info('GET /strongest success | result: %s = %s', strongest_code, rates[strongest_code])

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
    currencies = request.args.get('currencies', '')
    logger.info('GET /weakest | currencies: %s', currencies)

    if not currencies:
        logger.warning('GET /weakest | missing required parameter: currencies')
        return jsonify({'error': 'Parameter currencies is required'}), 400

    data = _fetch('live', {
        'source': BASE_CURRENCY,
        'currencies': currencies
    })

    if not data:
        logger.error('GET /weakest failed | currencies: %s', currencies)
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = {k[len(BASE_CURRENCY):]: v for k, v in data.get('quotes', {}).items()}

    if not rates:
        logger.warning('GET /weakest | no data for currencies: %s', currencies)
        return jsonify({'error': 'No data for selected currencies'}), 404

    weakest_code = min(rates, key=lambda c: rates[c])
    logger.info('GET /weakest success | result: %s = %s', weakest_code, rates[weakest_code])

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
    currencies = request.args.get('currencies', '')
    date_from  = request.args.get('date_from')
    date_to    = request.args.get('date_to')
    logger.info('GET /average | currencies: %s | from: %s | to: %s', currencies, date_from, date_to)

    if not all([currencies, date_from, date_to]):
        logger.warning('GET /average | missing parameters | currencies: %s | date_from: %s | date_to: %s',
                        currencies, date_from, date_to)
        return jsonify({'error': 'Required parameters: currencies, date_from, date_to'}), 400

    try:
        start = datetime.strptime(date_from, '%Y-%m-%d')
        end   = datetime.strptime(date_to, '%Y-%m-%d')
    except ValueError as e:
        logger.warning('GET /average | invalid date format: %s', e)
        return jsonify({'error': 'Date format must be YYYY-MM-DD'}), 400

    if start > end:
        logger.warning('GET /average | date_from (%s) is after date_to (%s)', date_from, date_to)
        return jsonify({'error': 'date_from cannot be after date_to'}), 400

    sums   = {}
    counts = {}
    current = start
    total_days = (end - start).days + 1
    fetched_days = 0

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        data = _fetch('historical', {
            'date': date_str,
            'source': BASE_CURRENCY,
            'currencies': currencies
        })

        if data:
            fetched_days += 1
            quotes = data.get('quotes', {})
            for key, value in quotes.items():
                code = key[len(BASE_CURRENCY):]
                sums[code]   = sums.get(code, 0) + value
                counts[code] = counts.get(code, 0) + 1
        else:
            logger.warning('GET /average | no data for date: %s — skipping', date_str)

        current += timedelta(days=1)

    if not sums:
        logger.error('GET /average | no data for entire period: %s — %s', date_from, date_to)
        return jsonify({'error': 'No data for the given period'}), 404

    averages = {code: round(sums[code] / counts[code], 6) for code in sums}
    logger.info('GET /average success | %d/%d days fetched | currencies: %s',
                fetched_days, total_days, list(averages.keys()))

    return jsonify({
        'base': BASE_CURRENCY,
        'date_from': date_from,
        'date_to': date_to,
        'days_counted': counts,
        'averages': averages
    })