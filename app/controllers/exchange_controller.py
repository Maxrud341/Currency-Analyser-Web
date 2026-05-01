import json
import os
import time
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
        time.sleep(1.1)
        return result
    except Exception as e:
        logger.error(f"[HISTORICAL] request failed date={date_str} error={e}")
        raise e


def _get_today_rates():
    today = datetime.now().strftime("%Y-%m-%d")
    return _fetch_historical_day(today)


@exchange_bp.route('/latest')
def latest():
    """Vrací aktuální kurzy pro zadané měny"""
    logger.info(f"[LATEST] endpoint called")

    currencies_param = request.args.get('currencies', '')
    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()] if currencies_param else []



    try:
        data = _get_today_rates()
    except Exception as e:
        logger.error(f"[LATEST] API error: {str(e)}")
        return jsonify({'error': 'Failed to fetch data'}), 502

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

    logger.info(f"[LATEST] Success: Fetched latest rates for base {BASE_CURRENCY}")
    return jsonify(response)


@exchange_bp.route('/strongest')
def strongest():
    """Hledá nejsilnější měnu z vybraného seznamu"""
    logger.info(f"[STRONGEST] endpoint called")

    currencies_param = request.args.get('currencies', '')
    base = request.args.get('base', BASE_CURRENCY).upper()

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    if not currencies:
        return jsonify({'error': 'Parametr currencies je povinný'}), 400

    try:
        data = _get_today_rates()
    except Exception:
        return jsonify({'error': 'Externí API je nedostupné'}), 500

    if not data:
        return jsonify({'error': 'Nepodařilo se získat data'}), 502

    rates = data.get("rates", {})

    base_rate = rates.get(base)
    if not base_rate:
        return jsonify({'error': 'Neplatná základní měna'}), 400

    filtered = {c: base_rate / rates[c] for c in currencies if c in rates and rates[c]}

    if not filtered:
        return jsonify({'error': 'Nebyly poskytnuty žádné platné měny'}), 400

    strongest_code = max(filtered, key=lambda c: filtered[c])

    return jsonify({
        "base": base,
        "strongest": {"currency": strongest_code, "rate": filtered[strongest_code]},
        "all_rates": filtered
    })


@exchange_bp.route('/historical-range')
def historical_range():
    """Vrací historické kurzy v zadaném časovém rozmezí"""
    logger.info(f"[HIST_RANGE] endpoint called")

    currencies_param = request.args.get('currencies', '')
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    base = request.args.get('base', BASE_CURRENCY).upper()

    if not all([currencies_param, date_from_str, date_to_str]):
        return jsonify({'error': 'Chybějící parametry'}), 400

    try:
        start = datetime.strptime(date_from_str, '%Y-%m-%d')
        end = datetime.strptime(date_to_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Neplatný formát data'}), 400

    if start > end:
        return jsonify({'error': 'Počáteční datum musí být dříve než koncové'}), 400

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    if len(currencies) != 1:
        return jsonify({'error': 'Zadejte přesně jednu cílovou měnu'}), 400

    target = currencies[0]
    result = {}
    current = start

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        try:
            day_data = _fetch_historical_day(date_str)
            if day_data:
                rates = day_data["rates"]
                t_val = rates.get(target)
                b_val = rates.get(base)
                result[date_str] = (t_val / b_val) if (t_val and b_val) else None
            else:
                result[date_str] = None
        except Exception:
            result[date_str] = None
        current += timedelta(days=1)

    return jsonify({
        "base": base, "target": target,
        "date_from": date_from_str, "date_to": date_to_str,
        "rates": result
    })


@exchange_bp.route('/average')
def average():
    """Počítá průměrný kurz pro dané měny v časovém období"""
    logger.info(f"[AVERAGE] endpoint called")

    currencies_param = request.args.get('currencies', '')
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    base = request.args.get('base', BASE_CURRENCY).upper()

    try:
        start = datetime.strptime(date_from_str, '%Y-%m-%d')
        end = datetime.strptime(date_to_str, '%Y-%m-%d')
        if start > end:
            return jsonify({'error': 'Neplatné časové rozmezí'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Neplatné parametry data'}), 400

    currencies = [c.strip().upper() for c in currencies_param.split(',') if c.strip()]
    sums = {c: 0.0 for c in currencies}
    counts = {c: 0 for c in currencies}

    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        try:
            day_data = _fetch_historical_day(date_str)
            if day_data:
                rates = day_data.get("rates", {})
                base_rate = rates.get(base)
                if base_rate:
                    for c in currencies:
                        t = rates.get(c)
                        if t is not None:
                            sums[c] += t / base_rate
                            counts[c] += 1
        except Exception:
            pass
        current += timedelta(days=1)

    averages = {c: round(sums[c] / counts[c], 6) for c in currencies if counts[c] > 0}
    return jsonify({
        "base": base, "date_from": date_from_str, "date_to": date_to_str,
        "days_counted": counts, "averages": averages
    })