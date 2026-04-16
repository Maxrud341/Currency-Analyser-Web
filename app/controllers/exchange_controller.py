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
    except Exception:
        logger.warning("[CACHE] load failed")
        return None


def _save_cache(key: str, data: dict):
    try:
        path = _cache_path(key)
        with open(path, 'w') as f:
            json.dump({'_cached_at': datetime.now().isoformat(), 'data': data}, f)
    except Exception:
        logger.warning("[CACHE] save failed")


def _daily_cache_key(date_str: str) -> str:
    return f"historical_all_{BASE_CURRENCY}_{date_str}"


def _fetch_historical_day(date_str: str):
    cached = _load_cache(_daily_cache_key(date_str))
    if cached:
        return cached

    params = {
        "access_key": API_KEY,
        "source": BASE_CURRENCY,
        "date": date_str
    }

    try:
        response = requests.get(f"{BASE_URL}/historical", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("success", True):
            logger.error(f"[HISTORICAL] API error date={date_str} response={data}")
            return None

        quotes = data.get("quotes", {})
        rates = {k[len(BASE_CURRENCY):]: v for k, v in quotes.items()}
        rates[BASE_CURRENCY] = 1.0

        result = {
            "timestamp": data.get("timestamp"),
            "rates": rates
        }

        _save_cache(_daily_cache_key(date_str), result)
        return result

    except Exception as e:
        logger.error(f"[HISTORICAL] request failed date={date_str} error={e}")
        return None


def _get_today_rates():
    today = datetime.now().strftime("%Y-%m-%d")
    return _fetch_historical_day(today)


@exchange_bp.route('/latest')
def latest():
    logger.info(f"[LATEST] endpoint called query={request.args.to_dict()}")

    currencies_param = request.args.get('currencies', '')
    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()] if currencies_param else []

    data = _get_today_rates()
    if not data:
        logger.error("[LATEST] failed to fetch data")
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = data.get("rates", {})
    all_rates = rates.copy()

    if currencies:
        all_rates = {c: all_rates.get(c) for c in currencies}

    response = {
        "base": BASE_CURRENCY,
        "timestamp": data.get("timestamp"),
        "rates": all_rates
    }

    logger.info(f"[LATEST] response={response}")
    return jsonify(response)


@exchange_bp.route('/strongest')
def strongest():
    logger.info(f"[STRONGEST] endpoint called query={request.args.to_dict()}")

    currencies_param = request.args.get('currencies', '')
    base = request.args.get('base', BASE_CURRENCY).upper()

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    if not currencies:
        logger.error("[STRONGEST] missing currencies")
        return jsonify({'error': 'Parameter currencies is required'}), 400

    data = _get_today_rates()
    if not data:
        logger.error("[STRONGEST] failed to fetch data")
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = data.get("rates", {})

    if base == BASE_CURRENCY:
        filtered = {c: 1 / rates[c] for c in currencies if c in rates}
    else:
        base_rate = rates.get(base)
        if not base_rate:
            logger.error(f"[STRONGEST] invalid base={base}")
            return jsonify({'error': 'Invalid base currency'}), 400
        filtered = {c: base_rate / rates[c] for c in currencies if c in rates}

    if not filtered:
        logger.error("[STRONGEST] no valid currencies")
        return jsonify({'error': 'No valid currencies provided'}), 400

    strongest_code = max(filtered, key=lambda c: filtered[c])

    response = {
        "base": base,
        "strongest": {
            "currency": strongest_code,
            "rate": filtered[strongest_code]
        },
        "all_rates": filtered
    }

    logger.info(f"[STRONGEST] response={response}")
    return jsonify(response)


@exchange_bp.route('/weakest')
def weakest():
    logger.info(f"[WEAKEST] endpoint called query={request.args.to_dict()}")

    currencies_param = request.args.get('currencies', '')
    base = request.args.get('base', BASE_CURRENCY).upper()

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    if not currencies:
        logger.error("[WEAKEST] missing currencies")
        return jsonify({'error': 'Parameter currencies is required'}), 400

    data = _get_today_rates()
    if not data:
        logger.error("[WEAKEST] failed to fetch data")
        return jsonify({'error': 'Failed to fetch data'}), 502

    rates = data.get("rates", {})

    if base == BASE_CURRENCY:
        filtered = {c: 1 / rates[c] for c in currencies if c in rates}
    else:
        base_rate = rates.get(base)
        if not base_rate:
            logger.error(f"[WEAKEST] invalid base={base}")
            return jsonify({'error': 'Invalid base currency'}), 400
        filtered = {c: base_rate / rates[c] for c in currencies if c in rates}

    if not filtered:
        logger.error("[WEAKEST] no valid currencies")
        return jsonify({'error': 'No valid currencies provided'}), 400

    weakest_code = min(filtered, key=lambda c: filtered[c])

    response = {
        "base": base,
        "weakest": {
            "currency": weakest_code,
            "rate": filtered[weakest_code]
        },
        "all_rates": filtered
    }

    logger.info(f"[WEAKEST] response={response}")
    return jsonify(response)


@exchange_bp.route('/historical-range')
def historical_range():
    logger.info(f"[HIST_RANGE] endpoint called query={request.args.to_dict()}")

    currencies_param = request.args.get('currencies', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    base = request.args.get('base', BASE_CURRENCY).upper()

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]

    if len(currencies) != 1:
        logger.error("[HIST_RANGE] invalid currencies count")
        return jsonify({'error': 'Provide exactly one currency'}), 400

    target = currencies[0]

    start = datetime.strptime(date_from, '%Y-%m-%d')
    end = datetime.strptime(date_to, '%Y-%m-%d')

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

            if target == base:
                result[date_str] = 1.0
            elif base == BASE_CURRENCY:
                result[date_str] = t
            else:
                b = rates.get(base)
                result[date_str] = (t / b) if (t and b) else None

        current += timedelta(days=1)



    response = {
        "base": base,
        "target": target,
        "date_from": date_from,
        "date_to": date_to,
        "rates": result
    }

    logger.info(f"[HIST_RANGE] response={response}")
    return jsonify(response)


@exchange_bp.route('/average')
def average():
    logger.info(f"[AVERAGE] endpoint called query={request.args.to_dict()}")

    currencies_param = request.args.get('currencies', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    base = request.args.get('base', BASE_CURRENCY).upper()

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]

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
                            sums[c] += t / base_rate
                            counts[c] += 1

        current += timedelta(days=1)

    averages = {c: round(sums[c] / counts[c], 6) for c in currencies if counts[c] > 0}

    response = {
        "base": base,
        "date_from": date_from,
        "date_to": date_to,
        "days_counted": counts,
        "averages": averages
    }

    logger.info(f"[AVERAGE] response={response}")
    return jsonify(response)