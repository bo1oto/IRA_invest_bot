import datetime
from typing import Union
from urllib.request import urlopen

import certifi
import json

api_key = '30f108d63e301c9f3ed49c75d138493b'

sp_requests = [
    "income-statement",
    "balance-sheet-statement",
    "cash-flow-statement",
    "financial-growth",
    "ratios",
    "enterprise-values"
]
requests = [
    "profile",
    "ratios-ttm",
    "key-metrics-ttm",
    "rating"
    # Есть ещё календари разные: отчёты (всех/компании), дивы, сплиты, экономика
    # Есть ещё пачка статистики: соц настроения, грейды, сюрпризы отчётов и ожидания аналитиков
    # Также имеется инсайдерская часть
    # Разумеется графики + индикаторы
    # Доля институционалов в компании
]

def download_data(ticker: str) -> list[Union[list, dict]]:
    data_arr = []
    req_body = 'https://financialmodelingprep.com/api/v3/'
    limit = 10
    for sp_req in sp_requests:
        url = f'{req_body}{sp_req}/{ticker}?period=quarter&limit={limit}&apikey={api_key}'
        data = execute_url(url)
        json.dump(data, open(f'\\FinancialData/Storage/{sp_req}.json', 'wt'))
        data_arr.append(data)
    for req in requests:
        url = f'{req_body}{req}/{ticker}?apikey={api_key}'
        data = execute_url(url)[0]
        json.dump(data, open(f'\\FinancialData/Storage/{req}.json', 'wt'))
        data_arr.append(data)
    return data_arr


def check_ticker(ticker: str) -> bool:
    return True if execute_url(f'https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={api_key}') else False

def get_last_report_data(ticker: str) -> str:
    url = f'https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=quarter&apikey={api_key}&limit=1'
    return execute_url(url)[0]["date"]

def get_profile(ticker: str) -> dict:
    url = f'https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={api_key}'
    return execute_url(url)[0]

def get_chart(ticker: str, days_count: int) -> list:
    url = f'https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?' \
          f'serietype=line&timeseries={days_count}&apikey={api_key}'
    return execute_url(url)["historical"]

def get_last_treasury() -> dict:
    today = datetime.datetime.today()
    risk_free_url = f'https://financialmodelingprep.com/api/v4/treasury?' \
                    f'from={(today + datetime.timedelta(days=-5)).strftime("%Y-%m-%d")}&' \
                    f'to={today.strftime("%Y-%m-%d")}&apikey={api_key}'
    return execute_url(risk_free_url)[0]

def get_dcf_data(ticker: str) -> tuple[float, list, list, list, list, list, dict]:
    url_body = 'https://financialmodelingprep.com/api/'
    market_premium_url = f'{url_body}v4/market_risk_premium?apikey={api_key}'
    estimates_url = f'{url_body}v3/analyst-estimates/{ticker}?limit=4&apikey={api_key}'
    years_limit = 5
    income_url = f'{url_body}v3/income-statement/{ticker}?limit={years_limit}&apikey={api_key}'
    cashflow_url = f'{url_body}v3/cash-flow-statement/{ticker}?limit={years_limit}&apikey={api_key}'
    balance_url = f'{url_body}v3/balance-sheet-statement/{ticker}?limit={years_limit}&apikey={api_key}'
    ev_url = f'{url_body}v3/enterprise-values/{ticker}?limit=1&apikey={api_key}'
    market_premium = execute_url(market_premium_url)
    estimates = execute_url(estimates_url)
    income = execute_url(income_url)
    cashflow = execute_url(cashflow_url)
    balance = execute_url(balance_url)
    ev = execute_url(ev_url)
    return get_last_treasury()['year10'] / 100, market_premium, estimates, income, cashflow, balance, ev

def execute_url(url: str) -> Union[list, dict]:
    response = urlopen(url, cafile=certifi.where())
    data = json.loads(response.read().decode('utf-8'))
    return data

