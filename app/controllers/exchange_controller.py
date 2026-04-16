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

os.makedirs(CACHE_DIR, exist_ok=True)

# ---------------------------------------------------------------
# CACHE HELPERS
# ---------------------------------------------------------------

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
        return cached['data']
    except Exception as e:
        logger.warning("[CACHE] Load failed: %s", e)
        return None

def _save_cache(key: str, data: dict):
    try:
        path = _cache_path(key)
        with open(path, 'w') as f:
            json.dump({'_cached_at': datetime.now().isoformat(), 'data': data}, f)
    except Exception as e:
        logger.warning("[CACHE] Save failed: %s", e)

# ---------------------------------------------------------------
# HISTORICAL FETCH
# ---------------------------------------------------------------

def _daily_cache_key(date_str: str) -> str:
    return f"historical_all_{BASE_CURRENCY}_{date_str}"

def _fetch_historical_day(date_str: str):
    logger.info("[HISTORICAL] Fetch day=%s", date_str)

    cached = _load_cache(_daily_cache_key(date_str))
    if cached:
        logger.info("[HISTORICAL] %s cache hit", date_str)
        return cached

    params = {
        "access_key": API_KEY,
        "source": BASE_CURRENCY,
        "date": date_str
    }

    url = f"{BASE_URL}/historical"

    try:
        response = requests.get(url, params=params, timeout=10)
        logger.info("[HISTORICAL] request url=%s status=%s", url, response.status_code)

        response.raise_for_status()
        data = response.json()

        if not data.get("success", True):
            logger.error("[HISTORICAL] API error %s payload=%s", date_str, data)
            return None

        quotes = data.get("quotes", {})
        rates = {k[len(BASE_CURRENCY):]: v for k, v in quotes.items()}
        rates[BASE_CURRENCY] = 1.0


        result = {
            "timestamp": data.get("timestamp"),
            "rates": rates
        }

        logger.info("[HISTORICAL] %s OK rates=%d", date_str, len(rates))
        _save_cache(_daily_cache_key(date_str), result)

        return result

    except Exception as e:
        logger.error("[HISTORICAL] ERROR %s %s", date_str, e)
        return None

def _get_today_rates():
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info("[TODAY] fetch rates date=%s", today)
    return _fetch_historical_day(today)

# ---------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------

@exchange_bp.route('/latest')
def latest():
    currencies_param = request.args.get('currencies', '')

    logger.info("[LATEST] request currencies=%s", currencies_param)

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()] if currencies_param else []

    data = _get_today_rates()
    if not data:
        logger.error("[LATEST] failed to fetch data")
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = data.get("rates", {})
    all_rates = rates.copy()

    if currencies:
        all_rates = {c: all_rates.get(c) for c in currencies}

    logger.info("[LATEST] success base=%s currencies=%d", BASE_CURRENCY, len(all_rates))

    return jsonify({
        'base': BASE_CURRENCY,
        'timestamp': data.get('timestamp'),
        'rates': all_rates
    })


@exchange_bp.route('/strongest')
def strongest():
    currencies_param = request.args.get('currencies', '')
    logger.info("[STRONGEST] request currencies=%s", currencies_param)

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    if not currencies:
        logger.warning("[STRONGEST] missing currencies")
        return jsonify({'error': 'Parameter currencies is required'}), 400

    data = _get_today_rates()
    if not data:
        logger.error("[STRONGEST] no data")
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = data.get("rates", {})
    filtered = {c: 1 / rates[c] for c in currencies if c in rates}

    if not filtered:
        logger.warning("[STRONGEST] empty filtered set")
        return jsonify({'error': 'No valid currencies provided'}), 400

    strongest_code = max(filtered, key=lambda c: filtered[c])

    logger.info("[STRONGEST] result=%s value=%s", strongest_code, filtered[strongest_code])

    return jsonify({
        'base': BASE_CURRENCY,
        'strongest': {
            'currency': strongest_code,
            'rate': filtered[strongest_code]
        },
        'all_rates': filtered
    })


@exchange_bp.route('/weakest')
def weakest():
    currencies_param = request.args.get('currencies', '')
    logger.info("[WEAKEST] request currencies=%s", currencies_param)

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    if not currencies:
        logger.warning("[WEAKEST] missing currencies")
        return jsonify({'error': 'Parameter currencies is required'}), 400

    data = _get_today_rates()
    if not data:
        logger.error("[WEAKEST] no data")
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = data.get("rates", {})
    filtered = {c: 1 / rates[c] for c in currencies if c in rates}

    if not filtered:
        logger.warning("[WEAKEST] empty filtered set")
        return jsonify({'error': 'No valid currencies provided'}), 400

    weakest_code = min(filtered, key=lambda c: filtered[c])

    logger.info("[WEAKEST] result=%s value=%s", weakest_code, filtered[weakest_code])

    return jsonify({
        'base': BASE_CURRENCY,
        'weakest': {
            'currency': weakest_code,
            'rate': filtered[weakest_code]
        },
        'all_rates': filtered
    })


@exchange_bp.route('/historical-range')
def historical_range():
    currencies_param = request.args.get('currencies', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    base = request.args.get('base', BASE_CURRENCY).upper()

    logger.info("[HIST_RANGE] currencies=%s from=%s to=%s base=%s",
                currencies_param, date_from, date_to, base)

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]

    if len(currencies) != 1:
        logger.warning("[HIST_RANGE] invalid currencies count=%d", len(currencies))
        return jsonify({'error': 'Provide exactly one currency'}), 400

    target = currencies[0]

    try:
        start = datetime.strptime(date_from, '%Y-%m-%d')
        end = datetime.strptime(date_to, '%Y-%m-%d')
    except Exception as e:
        logger.warning("[HIST_RANGE] invalid dates %s", e)
        return jsonify({'error': 'Invalid date format'}), 400

    result = {}
    current = start

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        day_data = _fetch_historical_day(date_str)

        if not day_data:
            result[date_str] = None
        else:
            rates = day_data["rates"]
            t = rates.get(target)

            if base == BASE_CURRENCY:
                result[date_str] = t
            else:
                b = rates.get(base)
                result[date_str] = (t / b) if (t and b) else None

        current += timedelta(days=1)

    logger.info("[HIST_RANGE] done points=%d", len(result))

    return jsonify({
        'base': base,
        'target': target,
        'date_from': date_from,
        'date_to': date_to,
        'rates': result
    })


@exchange_bp.route('/average')
def average():
    currencies_param = request.args.get('currencies', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    base = request.args.get('base', BASE_CURRENCY).upper()

    logger.info("[AVERAGE] currencies=%s from=%s to=%s base=%s",
                currencies_param, date_from, date_to, base)

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]

    if not all([currencies, date_from, date_to]):
        logger.warning("[AVERAGE] missing params")
        return jsonify({'error': 'Required parameters: currencies, date_from, date_to'}), 400

    start = datetime.strptime(date_from, '%Y-%m-%d')
    end = datetime.strptime(date_to, '%Y-%m-%d')

    sums = {c: 0.0 for c in currencies}
    counts = {c: 0 for c in currencies}

    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        day_data = _fetch_historical_day(date_str)

        if day_data:
            rates = day_data.get("rates", {})

            if base == BASE_CURRENCY:
                for c in currencies:
                    v = rates.get(c)
                    if v is not None:
                        sums[c] += v
                        counts[c] += 1
            else:
                base_rate = rates.get(base)
                if base_rate:
                    for c in currencies:
                        t = rates.get(c)
                        if t is not None:
                            v = t / base_rate
                            sums[c] += v
                            counts[c] += 1

        current += timedelta(days=1)

    averages = {c: round(sums[c] / counts[c], 6) for c in currencies if counts[c] > 0}

    logger.info("[AVERAGE] done computed=%d", len(averages))

    return jsonify({
        'base': base,
        'date_from': date_from,
        'date_to': date_to,
        'days_counted': counts,
        'averages': averages
    })