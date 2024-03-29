import json
import matplotlib.pyplot as plt
import time

from enum import Enum
from os import path, mkdir
from matplotlib import dates, ticker as tckr
from typing import Optional, Union

import network


class DataType(Enum):
    INCOME = 0
    BALANCE = 1
    CASHFLOW = 2
    FINANCIAL_G = 3
    RATIOS = 4
    ENTERPRISE = 5
    PROFILE = 6
    RATIOS_TTM = 7
    KEY_METRICS_TTM = 8
    RATING = 9


def get_growth(_from: float, _to: float) -> float:
    if (_from != 0.0) & (None not in [_from, _to]):
        dif = _to - _from
        return dif / abs(_from)
    else:
        return 0.0


class Company:
    data_path: str = '\\FinancialData/'
    countries: dict = json.load(open(f'{data_path}countries.json'))

    def __init__(self, _ticker, bot_version: str, _is_yoy: int = 0):
        self.ticker_str = _ticker
        self.version = bot_version

        self.data: list[Union[list, dict]] = list()
        self.old_ticker = dict()
        self.ticker = dict()
        self.old_industry = dict()
        self.industry = dict()
        self.industry_str = str()
        self.sector = dict()
        self.sector_str = str()
        self.ticker_path = str()
        self.industry_path = str()
        self.sector_path = str()
        self.all_tickers = dict()
        self.is_yoy = True if _is_yoy == 0 else False

        self.is_new_ticker, is_time_to_update = self.get_company_data()
        if is_time_to_update or bot_version > self.all_tickers[self.ticker_str]['version']:
            self.estimate_company()
        else:
            self.upload_data()

    def generate_report(self, config, lang_dict) -> str:

        def build(base: str, add: list, sign: list) -> str:
            for _add, _sign in zip(add, sign):
                base = base.replace(_sign, str(_add), 1)
            return base

        def to_lnum(input_num: float):
            patterns = ['', 'k', 'm', 'b']
            order = 0
            while abs(input_num) > 1000:
                input_num /= 1000
                order += 1
            return f'{str(round(input_num, 2))} {patterns[order]} $'

        def to_prc(num):
            return ('+' if num > 0.0 else '') + f'{str(round(num * 100, 2))}%' if num is not None else 'n/a'

        report: str = f'{self.ticker["name"]}\n\n'
        config_o = config['report']['other']
        dynamics = lang_dict['dynamics'][config['report']['dynamics']]

        key_s = self.ticker['key_statements']

        # Beta
        if config_o[1]:
            report += build(lang_dict['beta'], [str(self.ticker['beta'])], ['_'])
            report += '\n'

        # Рейтинг
        if config_o[2]:
            max_rate = str(10.0)
            report += build(lang_dict['rate'],
                            [str(self.ticker['base_rate']), max_rate],
                            ['_', '__']
                            )
            report += '\n'

        # Финансы
        config_f: list = config['report']['finance']
        if True in config_f:
            marks: list = [
                'revenue',
                'netIncome',
                'freeCashFlow'
            ]
            report += lang_dict["finance"]["base_line"]
            section_list = lang_dict["finance"]["data"]
            key_dynamic = 'growth_yoy' if config["report"]["dynamics"] == 0 else 'growth_qoq'
            for i in range(len(config_f)):
                if config_f[i]:
                    report += build(section_list[i],
                                    [to_lnum(key_s[marks[i]]['raw']), to_prc(key_s[marks[i]][key_dynamic]), dynamics],
                                    ['_', '__', '___']
                                    )
            report += '\n'

        # Баланс
        config_b: list = config['report']['balance']
        if True in config_b:
            marks: list = [
                "totalDebt",
                "cashAndCashEquivalents",
                "netDebt"
            ]
            report += lang_dict['balance']['base_line']
            section_list = lang_dict['balance']['data']
            key_dynamic = 'growth_yoy' if config['report']['dynamics'] == 0 else 'growth_qoq'
            for i in range(len(config_b)):
                if config_b[i]:
                    report += build(section_list[i],
                                    [to_lnum(key_s[marks[i]]['raw']), to_prc(key_s[marks[i]][key_dynamic]), dynamics],
                                    # тут поменять марку
                                    ['_', '__', '___']
                                    )
            report += '\n'

        # Дивиденды
        config_d = config['report']['div']
        if True in config_d:
            report += lang_dict['div']['base_line']
            key_dynamic = 'growth_yoy' if config['report']['dynamics'] == 0 else 'growth_qoq'
            if key_s['dividendYield']['raw'] is not None:
                if config_d[0]:
                    report += build(lang_dict['div']['yield'],
                                    [
                                        to_prc(key_s['dividendYield']['raw'])[1:],
                                        to_prc(key_s['dividendYield'][key_dynamic]),
                                        dynamics
                                    ],
                                    ['_', '__', '___']
                                    )
                if config_d[1]:
                    report += build(lang_dict['div']['yield'],
                                    [
                                        to_lnum(key_s['dividendYieldPerShare']['raw']),
                                        to_prc(key_s['dividendYieldPerShare'][key_dynamic]),
                                        dynamics
                                    ],
                                    ['_', '__', '___']
                                    )
            else:
                report += lang_dict['div']['none']
            report += '\n'

        config_v = config['report']['value']
        # Оценка
        if True in config_v:
            local_dict: dict = lang_dict['value']
            marks = [
                'peRatioTTM',
                'pegRatioTTM',
                'priceToSalesRatioTTM',
                'priceToBookRatioTTM',
                'priceToFreeCashFlowsRatioTTM'
            ]
            report += local_dict['base_line']
            templ_line: str = local_dict['template']
            compare_type: int = config['report']['value_type']
            for i, item in enumerate(config_v):
                if item:
                    add_arr = [local_dict['data'][i], self.ticker['indicators'][marks[i]]]
                    filler_arr = ['_'] * 2
                    if compare_type == 0:
                        add_arr.extend([self.industry['indicators'][marks[i]]['avg'],
                                        local_dict['value_type'][config['report']['value_type']],
                                        self.industry['tickers']['count']])
                        filler_arr.extend(['_'] * 3)
                    elif compare_type == 1:
                        add_arr.extend([self.sector['indicators'][marks[i]]['avg'],
                                        local_dict['value_type'][config['report']['value_type']],
                                        self.sector['tickers']['count']])
                        filler_arr.extend(['_'] * 3)
                    elif compare_type == 2:
                        templ_line = templ_line[:5] + '\n'
                    report += build(templ_line, add_arr, filler_arr)
            report += '\n'

        # DCF
        if config_o[0]:
            add_line = f'{str(round(self.ticker["dcf"], 2))} $' \
                if self.ticker["dcf"] is not None else lang_dict['dcf']['no_data']
            report += build(lang_dict['dcf']['base_line'], [add_line], ['_'])

        return report

    def generate_chart(self) -> str:
        plot_path = f'{self.data_path}Plots/{self.ticker_str}.png'

        if path.exists(plot_path):  # работает только для дневок
            last_plt_upd = time.gmtime(path.getmtime(plot_path))
            time_now = time.gmtime()
            if (last_plt_upd.tm_year == time_now.tm_year) & \
                    (last_plt_upd.tm_mon == time_now.tm_mon) & \
                    (
                            (last_plt_upd.tm_wday == time_now.tm_wday) |
                            ((time_now.tm_wday in (0, 1)) & (last_plt_upd.tm_wday in (6, 0)))
                    ):
                return plot_path

        chart = network.get_chart(self.ticker_str, 365)
        date_list = []
        data_list = []
        for elem in reversed(chart):
            data_list.append(round(elem["close"], 2))
            date_list.append(dates.datestr2num(elem["date"]))

        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        ax.set_title(f'{self.ticker["ticker"]}, {self.ticker["name"]}', loc='left', y=0.9, x=0.01,
                     fontsize=20, backgroundcolor='white')
        # X-axis
        ax.xaxis.set_major_formatter(dates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(dates.MonthLocator())
        # ax.xaxis.set_minor_formatter(dates.DateFormatter("%b"))
        # ax.xaxis.set_minor_locator(matplotlib.dates.MonthLocator())
        # Y-axis
        order = (str(round(max(data_list))).__len__() - 2)
        if order == 0:
            order = 1
        ax.yaxis.set_major_locator(tckr.MultipleLocator(10 ** order))
        ax.yaxis.set_minor_locator(tckr.MultipleLocator((10 ** order) / 2))

        ax.plot(date_list, data_list)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        ax.axhline(data_list[-1], color='gray', linestyle='--', linewidth=0.6)
        ax.text(date_list[-1] + 30, data_list[-1], str(data_list[-1]), size=10,
                ha="center", va="center",
                bbox=dict(boxstyle="round",
                          facecolor='white'
                          )
                )
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.yaxis.tick_right()
        # plt.grid()

        fig.savefig(plot_path, bbox_inches='tight')
        fig.clf()
        return plot_path

    def prepare_data(self):
        if not path.exists(f'{Company.data_path}{self.sector_str}'):
            mkdir(f'{Company.data_path}{self.sector_str}')
        if not path.exists(f'{Company.data_path}{self.sector_str}/{self.industry_str}'):
            mkdir(f'{Company.data_path}{self.sector_str}/{self.industry_str}')

        self.sector_path = f'{Company.data_path}{self.sector_str}/_{self.sector_str}.json'
        self.industry_path = f'{Company.data_path}{self.sector_str}/{self.industry_str}/_{self.industry_str}.json'
        self.ticker_path = f'{Company.data_path}{self.sector_str}/{self.industry_str}/{self.ticker_str}.json'

        if not self.is_new_ticker:
            self.old_ticker = json.load(open(self.ticker_path, 'rt', encoding='utf-8'))
        if path.exists(self.sector_path):
            self.sector = json.load(open(self.sector_path, 'rt', encoding='utf-8'))
        if path.exists(self.industry_path):
            self.old_industry = json.load(open(self.industry_path, 'rt', encoding='utf-8'))

    # Есть некоторая погрешность из-за none значений, потом поправлю путём пересчёта по тикерам
    def upgrade_average_industry(self) -> None:
        if self.old_industry:
            if self.is_new_ticker:
                for iname in self.industry['indicators']:
                    if self.ticker['indicators'][iname] is not None:
                        self.industry['indicators'][iname] = {
                            'avg': round(
                                (self.industry['indicators'][iname]['avg'] + self.ticker['indicators'][iname]) / 2, 2),
                            'acc': self.industry['indicators'][iname]['acc'] + self.ticker['indicators'][iname]
                        }
            else:
                for iname in self.industry["indicators"]:
                    if self.ticker["indicators"][iname] is not None:
                        dif: float = self.ticker["indicators"][iname] - self.old_ticker["indicators"][iname] \
                            if self.old_ticker["indicators"][iname] is not None else self.ticker["indicators"][iname]
                        self.industry["indicators"][iname]["acc"] = self.industry["indicators"][iname]["acc"] + dif
                        self.industry["indicators"][iname]["avg"] = round(
                            self.industry["indicators"][iname]["acc"] / self.industry["tickers"]["count"], 2)
        else:
            for iname in self.ticker["indicators"]:
                if self.ticker["indicators"][iname] is not None:
                    self.industry["indicators"][iname] = {
                        "avg": self.ticker["indicators"][iname],
                        "acc": self.ticker["indicators"][iname]
                    }
                else:
                    self.industry["indicators"][iname] = {'avg': 0.0, 'acc': 0.0}

    # Есть некоторая погрешность из-за none значений, потом поправлю путём пересчёта по индустриям
    def upgrade_average_sector(self, is_new_sector) -> None:
        if not is_new_sector:
            if self.old_industry:
                for iname in self.sector["indicators"]:
                    dif: float = self.industry["indicators"][iname]["acc"] - \
                                 self.old_industry["indicators"][iname]["acc"] \
                        if self.old_industry["indicators"][iname]["acc"] is not None \
                        else self.industry["indicators"][iname]["acc"]
                    self.sector["indicators"][iname]["acc"] = self.sector["indicators"][iname]["acc"] + dif
                    self.sector["indicators"][iname]["avg"] = round(
                        self.industry["indicators"][iname]["acc"] / self.sector["industries"]["count"], 2)
            else:
                for iname in self.sector["indicators"]:
                    self.sector["indicators"][iname] = {
                        "avg": (self.sector["indicators"][iname]["avg"] +
                                round(self.industry["indicators"][iname]["acc"]) / 2, 2),
                        "acc": self.sector["indicators"][iname]["acc"] + self.industry["indicators"][iname]["acc"]
                    }
        else:
            for iname in self.industry["indicators"]:
                self.sector["indicators"][iname] = {
                    "avg": self.industry["indicators"][iname]["avg"],
                    "acc": self.industry["indicators"][iname]["acc"]
                }

    def upgrade_sector_json(self, is_new_industry) -> None:
        if self.sector:
            is_new_sector = False
            self.sector["lastUpdate"] = self.ticker["lastUpdate"]
            if is_new_industry:
                self.sector["base_rate"] = {
                    "avg": round((self.sector["base_rate"]["avg"] + self.industry["base_rate"]["avg"]) / 2, 2),
                    "acc": self.sector["base_rate"]["acc"] + self.industry["base_rate"]["avg"]
                }
                self.sector["industries"] = {
                    "count": self.sector["industries"]["count"] + 1,
                    "data": self.sector["industries"]["data"] + [self.industry_str]
                }
                self.sector["tickers"] = {
                    "count": self.sector["tickers"]["count"] + 1,
                    "data": self.sector["tickers"]["data"] + [self.ticker_str]
                }
            else:
                self.sector["base_rate"]["acc"] = self.sector["base_rate"]["acc"] + \
                                                  self.industry["base_rate"]["avg"] - \
                                                  self.old_industry["base_rate"]["avg"]
                self.sector["base_rate"]["avg"] = round(self.sector["base_rate"]["acc"]
                                                        / self.sector["industries"]["count"], 2)
                if self.is_new_ticker:
                    self.sector["tickers"].update({
                        "count": self.sector["tickers"]["count"] + 1,
                        "data": self.sector["tickers"]["data"] + [self.ticker_str]
                    })
        else:
            is_new_sector = True
            self.sector = {
                'industries': {
                    "count": 1,
                    "data": [self.industry_str]
                },
                'tickers': {
                    "count": 1,
                    "data": [self.ticker_str]
                },
                'lastUpdate': self.ticker["lastUpdate"],
                'base_rate': {
                    "avg": self.industry["base_rate"]["avg"],
                    "acc": self.industry["base_rate"]["acc"]
                },
                'indicators': {}
            }
        self.upgrade_average_sector(is_new_sector)

    def upgrade_industry_json(self) -> None:
        if self.old_industry:
            is_new_industry = False
            self.industry = dict(self.old_industry)
            self.industry["lastUpdate"] = self.ticker["lastUpdate"]
            if self.is_new_ticker:
                self.industry["base_rate"] = {
                    "avg": round((self.industry["base_rate"]["avg"] + self.ticker["base_rate"]) / 2.0, 2),
                    "acc": self.industry["base_rate"]["acc"] + self.ticker["base_rate"]
                }
                self.industry["tickers"] = {
                    "count": self.industry["tickers"]["count"] + 1,
                    "data": self.industry["tickers"]["data"] + [self.ticker_str]
                }
            else:
                self.industry["base_rate"]["acc"] = self.industry["base_rate"]["acc"] + \
                                                    self.ticker["base_rate"] - self.old_ticker["base_rate"]
                self.industry["base_rate"]["avg"] = round(
                    self.industry["base_rate"]["acc"] / self.industry["tickers"]["count"], 2)
        else:
            is_new_industry = True
            self.industry = {
                'tickers': {
                    'count': 1,
                    'data': [self.ticker_str]
                },
                'lastUpdate': self.ticker["lastUpdate"],
                'base_rate': {
                    'avg': self.ticker["base_rate"],
                    'acc': self.ticker["base_rate"]
                },
                'indicators': {}
            }
        self.upgrade_average_industry()
        self.upgrade_sector_json(is_new_industry)

    def upgrade_ticker_json(self) -> None:
        self.ticker = {
            'name': self.data[DataType.PROFILE.value]['companyName'],
            'ticker': self.ticker_str,
            'beta': self.data[DataType.PROFILE.value]['beta'],
            'base_rate': round(self.get_base_rate, 2),
            'relative_rate': {},
            'dcf': self.compute_dcf,
            'lastUpdate': round(time.time()),
            'key_statements': self.get_key_statements,
            'indicators': self.get_indicators
        }
        self.upgrade_industry_json()
        self.ticker['relative_rate'] = self.get_relative_rate(self.ticker['base_rate'], self.ticker['indicators'])

    def remove_ticker(self):
        sector_str = self.all_tickers[self.ticker_str]['sector']
        industry_str = self.all_tickers[self.ticker_str]['industry']
        sector_path = f'{Company.data_path}{sector_str}/_{sector_str}.json'
        industry_path = f'{Company.data_path}{sector_str}/{industry_str}/_{industry_str}.json'
        ticker_path = f'{Company.data_path}{sector_str}/{industry_str}/{self.ticker_str}.json'

        ticker = json.load(open(ticker_path, 'rt', encoding='utf-8'))
        sector = json.load(open(sector_path, 'rt', encoding='utf-8'))
        industry = json.load(open(industry_path, 'rt', encoding='utf-8'))
        industry['tickers']['count'] -= 1
        industry['tickers']['data'].remove(self.ticker_str)
        industry['base_rate']['acc'] -= ticker['base_rate']
        industry['base_rate']['avg'] = round(industry['base_rate']['acc'] / industry['tickers']['count'], 2)
        for element in industry['indicators']:
            industry['indicators'][element]['acc'] -= ticker['indicators'][element]
            industry['indicators'][element]['avg'] = round(industry['indicators'][element]['acc'] /
                                                           industry['tickers']['count'], 4)

        sector['tickers']['count'] -= 1
        sector['tickers']['data'].remove(self.ticker_str)
        sector['base_rate']['acc'] -= industry['base_rate']['avg']
        sector['base_rate']['avg'] = round(sector['base_rate']['acc'] / sector['tickers']['count'], 2)
        for element in industry['indicators']:
            sector['indicators'][element]['acc'] -= industry['indicators'][element]['avg']
            sector['indicators'][element]['avg'] = round(sector['indicators'][element]['acc'] /
                                                         sector['tickers']['count'], 4)
        os.remove(ticker_path)
        self.is_new_ticker = True
        json.dump(sector, open(sector_path, 'wt', encoding='utf-8'))
        json.dump(industry, open(industry_path, 'wt', encoding='utf-8'))

    @property
    def compute_dcf(self) -> Optional[float]:
        import numpy as np
        risk_free, market_rate_all, estimates, income, cashflow, balance, ev = network.get_dcf_data(self.ticker_str)
        if ev:
            ev = ev[0]
        else:
            return None
        profile = network.get_profile(self.ticker_str)
        if len(income) < 5:
            return None

        income.reverse()
        cashflow.reverse()
        balance.reverse()
        estimates.reverse()

        # Base
        ebit: list = [data["operatingIncome"] for data in income]
        tax_rate = abs(income[-1]["incomeTaxExpense"]) / ebit[-1] if ebit[-1] > 0.0 else 0.0
        rev: list = [data["revenue"] for data in income]
        d_a: list = [data["depreciationAndAmortization"] for data in income]
        cap_ex: list = [abs(data["capitalExpenditure"]) for data in cashflow]
        nwc: list = [data["netReceivables"] + data["inventory"] -
                     data["accountPayables"] - data['deferredRevenue'] for data in balance]
        for i in (rev, cap_ex):
            if 0.0 in i:
                return None

        last_rep_year = time.strptime(income[-1]["date"], '%Y-%m-%d').tm_year
        est_year = time.strptime(estimates[0]["date"], '%Y-%m-%d').tm_year if estimates else last_rep_year + 1
        while last_rep_year >= est_year:
            estimates = estimates[1:]
            est_year = time.strptime(estimates[0]["date"], '%Y-%m-%d').tm_year

        # Revenue
        rev_g = [get_growth(rev[i], item) for i, item in enumerate(rev[1:])]
        rev_est = []
        rev_est_g = []
        if estimates:
            rev_est = [(est["estimatedRevenueLow"] + est["estimatedRevenueHigh"]) / 2 for est in estimates]
            rev_est_g = [get_growth(rev[-1], rev_est[0])] + \
                        [get_growth(rev_est[i - 1], rev_est[i]) for i in range(1, len(rev_est))]

        rev_g_ma = 0.0
        rev_all_g = rev_g + rev_est_g
        years = len(rev_all_g) + 1
        for i, value in enumerate(rev_all_g):
            rev_g_ma = rev_g_ma * (1 - ((1 + i) / years)) + value * ((1 + i) / years)

        # EBIT
        ebit_prc = [_ebit / _rev for _ebit, _rev in zip(ebit, rev)]
        ebit_prc_g = [get_growth(ebit_prc[i], item) for i, item in enumerate(ebit_prc[1:])]
        ebit_est_prc = []
        ebit_est_prc_g = []
        if estimates:
            ebit_est = [(est["estimatedEbitLow"] + est["estimatedEbitHigh"]) / 2 for est in estimates]
            ebit_est_prc = [_ebit_est / _rev_est for _ebit_est, _rev_est in zip(ebit_est, rev_est)]
            ebit_est_prc_g = [get_growth(ebit_prc[-1], ebit_est_prc[0])] + \
                             [get_growth(ebit_est_prc[i], item) for i, item in enumerate(ebit_est_prc[1:])]

        ebit_prc_ma = 0.0
        ebit_prc_all = ebit_prc + ebit_est_prc
        years = len(ebit_prc_all) + 1
        for i, value in enumerate(ebit_prc_all):
            ebit_prc_ma = ebit_prc_ma * (1 - ((1 + i) / years)) + value * ((1 + i) / years)

        ebit_prc_g_ma = 0.0
        ebit_prc_all_g = ebit_prc_g + ebit_est_prc_g
        years = len(ebit_prc_all_g) + 1
        for i, value in enumerate(ebit_prc_all_g):
            ebit_prc_g_ma = ebit_prc_g_ma * (1 - ((1 + i) / years)) + value * ((1 + i) / years)

        last_ebit_prc = ebit_prc_ma + (abs(ebit_prc_ma) * ebit_prc_g_ma)

        # CapEx
        cap_ex_prc = [_cap_ex / _rev for _cap_ex, _rev in zip(cap_ex, rev)]

        years = len(cap_ex_prc) + 1
        cap_ex_prc_ma = 0.0
        for i, value in enumerate(cap_ex_prc):
            cap_ex_prc_ma = cap_ex_prc_ma * (1 - (2 / years)) + value * (2 / years)

        # D&A
        d_a_prc = [_d_a / _cap_ex for _d_a, _cap_ex in zip(d_a, cap_ex)]

        years = len(d_a_prc) + 1
        d_a_prc_ma = 0.0
        for i, value in enumerate(d_a_prc):
            d_a_prc_ma = d_a_prc_ma * (1 - (2 / years)) + value * (2 / years)

        # NWC
        nwc_prc = [item / rev[i] for i, item in enumerate(nwc)]
        nwc_prc_g = [get_growth(nwc_prc[i], item) for i, item in enumerate(nwc_prc[1:])]

        years = len(nwc_prc) + 1
        nwc_prc_ma = 0.0
        for i, value in enumerate(nwc_prc):
            nwc_prc_ma = nwc_prc_ma * (1 - ((1 + i) / years)) + value * ((1 + i) / years)

        years = len(nwc_prc_g) + 1
        nwc_prc_g_ma = 0.0
        for i, value in enumerate(nwc_prc_g):
            nwc_prc_g_ma = nwc_prc_g_ma * (1 - ((1 + i) / years)) + value * ((1 + i) / years)

        last_nwc_prc = nwc_prc_ma + (abs(nwc_prc_ma) * nwc_prc_g_ma)

        # Calculate full data
        rev = [rev[-1]]
        for i in range(10):
            rev.append(round(rev[i] * (1 + rev_g_ma)))
        ebit.clear()
        for i, _ebit_prc in enumerate((np.linspace(ebit_prc[-1], last_ebit_prc, 11)).real):
            ebit.append(round(rev[i] * _ebit_prc))
        cap_ex = [round(cap_ex_prc_ma * item) for item in rev[1:]]
        d_a = [round(d_a_prc_ma * item) for item in cap_ex]
        nwc.clear()
        for i, _c_nwc_prc in enumerate((np.linspace(nwc_prc[-1], last_nwc_prc, 11)).real):
            nwc.append(round(rev[i] * _c_nwc_prc))
        c_nwc = [item - nwc[i] for i, item in enumerate(nwc[1:])]

        rev = rev[1:]
        ebit = ebit[1:]
        # WACC
        market_rate = 0.08
        for country in market_rate_all:
            if country['country'] == Company.countries[profile['country']]:
                market_rate = country['totalEquityRiskPremium'] / 100
                break
        beta = profile["beta"]
        equity = balance[-1]["totalEquity"]
        cost_of_equity = risk_free + beta * market_rate
        debt = balance[-1]["totalDebt"]
        cost_of_debt = abs(income[-1]["interestExpense"]) / balance[-1]["totalDebt"] \
            if balance[-1]["totalDebt"] != 0.0 else 0.0

        wacc = (equity / (equity + debt)) * cost_of_equity + (debt / (equity + debt)) * cost_of_debt * (1 - tax_rate)

        # Terminal values and UFCF
        terminal_growth_rate = 0.025

        u_fcf = [round(ebit[i] * (1 - tax_rate) + d_a[i] - cap_ex[i] - c_nwc[i]) for i in range(len(rev))]

        terminl_value = round((u_fcf[-1] * (1 + terminal_growth_rate)) / (wacc - terminal_growth_rate))
        present_value_fcf = [round(item / ((1 + wacc) ** (i + 1))) for i, item in enumerate(u_fcf)]
        present_value_tv = round(terminl_value / ((1 + wacc) ** 10))
        pv_ev = sum(present_value_fcf) + present_value_tv
        cash = ev["minusCashAndCashEquivalents"]
        shares = ev["numberOfShares"]
        if shares == 0:
            return None
        price = (pv_ev + cash - debt) / shares
        return round(price, 2)

    @property
    def get_base_rate(self) -> float:
        ratios = self.data[DataType.RATIOS.value][0]
        income = self.data[DataType.INCOME.value][0]
        balance = self.data[DataType.BALANCE.value][0]
        cash_flows = self.data[DataType.CASHFLOW.value][0]
        fin_g = self.data[DataType.FINANCIAL_G.value]

        # Profit block
        profit_score = 0.0
        if cash_flows["freeCashFlow"] > 0.0:
            profit_score += 1.25
        if income["netIncome"] > 0.0:
            profit_score += 1.0
        if income["revenue"] > 0.0:
            profit_score += 0.25

        # Debt block
        debt_score = 0.0
        if (balance['totalEquity'] != 0.0) and (balance['totalDebt'] / balance['totalEquity'] < 1.2):
            debt_score += 0.7
        if balance['totalDebt'] / balance['totalAssets'] < 0.8:
            debt_score += 0.3
        if (ratios['currentRatio'] is not None) and (ratios['currentRatio'] > 1.0):
            debt_score += 0.75
        if (ratios['currentRatio'] is not None) and (ratios['quickRatio'] > 1.0):
            debt_score += 0.5
        if (ratios['currentRatio'] is not None) and (ratios['cashRatio'] > 1.0):
            debt_score += 0.25

        # Div block
        treasury = network.get_last_treasury()
        if ratios["dividendYield"] is not None:
            if ratios["dividendYield"] > treasury['year10']:
                div_score = 2.5
            elif ratios["dividendYield"] > treasury['year5']:
                div_score = 1.5
            else:
                div_score = 0.5
        else:
            div_score = 0.0

        # Growth block
        key_metrics = [
            "revenueGrowth",
            "netIncomeGrowth",
            "freeCashFlowGrowth",
            "dividendsperShareGrowth",
            "bookValueperShareGrowth"
        ]
        growth_score = 1.25
        for metric in key_metrics:
            avg_growth = sum([_fin_g[metric] for _fin_g in fin_g]) / 4
            if avg_growth >= 0.1:
                growth_score = 2.5
            elif avg_growth <= -0.05:
                growth_score = 0.0
        return profit_score + debt_score + div_score + growth_score

    @property
    def get_indicators(self) -> dict:
        ratios = self.data[DataType.RATIOS_TTM.value]
        key_metric = self.data[DataType.KEY_METRICS_TTM.value]

        '''
        # "marketCapTTM",
        # "enterpriseValueTTM",
        # "incomeQualityTTM",# доля основного бизнеса в общей прибыли, мне кажется он может пригодиться, но не сейчас
        # "salesGeneralAndAdministrativeToRevenueTTM",
        # "researchAndDevelopementToRevenueTTM", для сравнения не надо, но может пригодиться просто
        # "capexToRevenueTTM",
        # "capexToDepreciationTTM",
        # "stockBasedCompensationToRevenueTTM", # процент выручки, выплачиваемый сотрудникам в качестве опционов
        # может быть интересным показателем, но не в сравнении с сектором
        # "capexPerShareTTM"
        '''
        ratio_str = [
            "freeCashFlowPerShareTTM",
            "cashPerShareTTM",
            "shortTermCoverageRatiosTTM",  # покрытие короткого долга операционным потоком
            "currentRatioTTM",
            "quickRatioTTM",
            "cashRatioTTM",
            "inventoryTurnoverTTM",  # чем больше показатель, тем больше раз компания реализовала свой инвентарь
            "grossProfitMarginTTM",  # эффективность производства товара или услуги
            "operatingProfitMarginTTM",  # эффективность предприятия как такового
            "returnOnAssetsTTM",
            "returnOnEquityTTM",
            "returnOnCapitalEmployedTTM",
            "receivablesTurnoverTTM",  # чем больше показатель,
            # тем меньшую часть выручки составляют неоплаченные счета
            "capitalExpenditureCoverageRatioTTM",  # чем больше показатель, тем более "завод окупает своё содержание"
            "payoutRatioTTM",  # какая часть от чистой прибыли идёт на дивиденды
            "dividendPerShareTTM",
            "dividendYieldTTM",
            "dividendPaidAndCapexCoverageRatioTTM",
            "cashFlowToDebtRatioTTM",  # Насколько операционный поток покрывает долг
            "payablesTurnoverTTM",  # нет точных данных, но по идее аналогично:
            # чем больше показатель, тем меньше компания задолжала поставщикам
            "interestCoverageTTM",
            # как долго комания может обслуживать проценты по долгу из своего основного бизнеса
            "cashConversionCycleTTM",  # чем меньше, тем быстрее в компании происходит денежный оборот
            "debtEquityRatioTTM",
            "pegRatioTTM",
            "peRatioTTM",
            "priceToBookRatioTTM",
            "priceToSalesRatioTTM",
            "priceToFreeCashFlowsRatioTTM",
            "priceToOperatingCashFlowsRatioTTM",
            "enterpriseValueMultipleTTM"
        ]
        key_metric_str = [
            "revenuePerShareTTM",
            "netIncomePerShareTTM",
            "roicTTM",
            "interestDebtPerShareTTM",
            "debtToAssetsTTM",
            "netDebtToEBITDATTM"
        ]

        final_dict = {}
        for elem in ratio_str:
            final_dict[elem] = 0.0 if ratios[elem] is None else round(ratios[elem], 2)
        for elem in key_metric_str:
            final_dict[elem] = 0.0 if key_metric[elem] is None else round(key_metric[elem], 2)

        return final_dict

    @property
    def get_key_statements(self) -> dict:
        def get_yoy_growth(data: list, name: str) -> Optional[float]:
            return round(get_growth(data[4][name], data[0][name]), 4) \
                if (len(data) >= 5) and (None not in [data[4][name], data[0][name]]) else None

        def get_qoq_growth(data: list, name: str) -> Optional[float]:
            return round(get_growth(data[1][name], data[0][name]), 4) \
                if (len(data) >= 2) and (None not in [data[1][name], data[0][name]]) else None

        income = self.data[DataType.INCOME.value]
        balance = self.data[DataType.BALANCE.value]
        cashflow = self.data[DataType.CASHFLOW.value]
        ratios = self.data[DataType.RATIOS.value]
        ev = self.data[DataType.ENTERPRISE.value]

        key_statements = {
            'revenue': {
                'raw': income[0]['revenue'],
                'growth_yoy': get_yoy_growth(income, 'revenue'),
                'growth_qoq': get_qoq_growth(income, 'revenue'),
            },
            'netIncome': {
                'raw': income[0]['netIncome'],
                'growth_yoy': get_yoy_growth(income, 'netIncome'),
                'growth_qoq': get_qoq_growth(income, 'netIncome'),
            },
            'freeCashFlow': {
                'raw': cashflow[0]['freeCashFlow'],
                'growth_yoy': get_yoy_growth(cashflow, 'freeCashFlow'),
                'growth_qoq': get_qoq_growth(cashflow, 'freeCashFlow'),
            },
            'totalDebt': {
                'raw': balance[0]['totalDebt'],
                'growth_yoy': get_yoy_growth(balance, 'totalDebt'),
                'growth_qoq': get_qoq_growth(balance, 'totalDebt'),
            },
            'cashAndCashEquivalents': {
                'raw': balance[0]['cashAndCashEquivalents'],
                'growth_yoy': get_yoy_growth(balance, 'cashAndCashEquivalents'),
                'growth_qoq': get_qoq_growth(balance, 'cashAndCashEquivalents'),
            },
            'netDebt': {
                'raw': balance[0]['netDebt'],
                'growth_yoy': get_yoy_growth(balance, 'netDebt'),
                'growth_qoq': get_qoq_growth(balance, 'netDebt'),
            },
            'dividendYield': {
                'raw': ratios[0]['dividendYield'],
                'growth_yoy': get_yoy_growth(ratios, 'dividendYield'),
                'growth_qoq': get_qoq_growth(ratios, 'dividendYield'),
            },
            'dividendYieldPerShare': {
                'raw': ratios[0]['dividendYield'] * ev[0]['stockPrice']
                if ratios[0]['dividendYield'] is not None else None,
                'growth_yoy': get_growth(ratios[4]['dividendYield'] * ev[4]['stockPrice'],
                                         ratios[0]['dividendYield'] * ev[0]['stockPrice'])
                if (len(ratios) >= 5) and
                   (None not in [ratios[4]['dividendYield'], ratios[0]['dividendYield']]) else None,
                'growth_qoq': get_growth(ratios[1]['dividendYield'] * ev[0]['stockPrice'],
                                         ratios[0]['dividendYield'] * ev[0]['stockPrice'])
                if (len(ratios) >= 2) and
                   (None not in [ratios[1]['dividendYield'], ratios[0]['dividendYield']]) else None
            }
        }
        return key_statements

    def get_relative_rate(self, base_rate: float, ratios: dict) -> dict:
        up_ratio = {
            'freeCashFlowPerShareTTM',
            'cashPerShareTTM',
            'shortTermCoverageRatiosTTM',  # покрытие короткого долга операционным потоком
            'currentRatioTTM',
            'quickRatioTTM',
            'cashRatioTTM',
            'inventoryTurnoverTTM',  # чем больше показатель, тем больше раз компания реализовала свой инвентарь
            'grossProfitMarginTTM',  # эффективность производства товара или услуги
            'operatingProfitMarginTTM',  # эффективность предприятия как такового
            'returnOnAssetsTTM',
            'returnOnEquityTTM',
            'returnOnCapitalEmployedTTM',
            'receivablesTurnoverTTM',  # чем больше показатель,
            # тем меньшую часть выручки составляют неоплаченные счета
            'capitalExpenditureCoverageRatioTTM',
            # чем больше показатель, тем более "завод окупает своё содержание"
            'revenuePerShareTTM',
            'netIncomePerShareTTM',
            'roicTTM',
            'payoutRatioTTM',  # какая часть от чистой прибыли идёт на дивиденды
            'dividendPerShareTTM',
            'dividendYieldTTM',
            'dividendPaidAndCapexCoverageRatioTTM',
            'cashFlowToDebtRatioTTM',  # Насколько операционный поток покрывает долг
            'payablesTurnoverTTM',  # нет точных данных, но по идее аналогично:
            # чем больше показатель, тем меньше компания задолжала поставщикам
            'interestCoverageTTM',
            # как долго комания может обслуживать проценты по долгу из своего основного бизнеса
        }
        low_ratio = {
            'cashConversionCycleTTM',  # чем меньше, тем быстрее в компании происходит денежный оборот
            'debtEquityRatioTTM',
            'interestDebtPerShareTTM',
            'debtToAssetsTTM',
            'netDebtToEBITDATTM',
            'pegRatioTTM',
            'peRatioTTM',
            'priceToBookRatioTTM',
            'priceToSalesRatioTTM',
            'priceToFreeCashFlowsRatioTTM',
            'priceToOperatingCashFlowsRatioTTM',
            'enterpriseValueMultipleTTM'
        }

        def get_rates(rel_indic: dict) -> float:
            rate: float = 0.0
            for element in up_ratio:
                rate += get_growth(rel_indic[element]['avg'], ratios[element])
            for element in low_ratio:
                rate += get_growth(rel_indic[element]['avg'], ratios[element])
            return round(rate / (len(up_ratio) + len(low_ratio)), 4)

        rates: dict[str, dict[str, Optional[float]]] = {
            'base': {
                'industry': None,
                'sector': None
            },
            'wide': {
                'industry': None,
                'sector': None
            }
        }

        if self.industry['tickers']['count'] >= 5:
            ind_indic = self.industry['indicators']
            rates['wide']['industry'] = get_rates(ind_indic)
            rates['base']['industry'] = round(get_growth(base_rate, self.industry['base_rate']['avg']), 4)
        if self.sector["tickers"]["count"] >= 10:
            sec_indic = self.sector["indicators"]
            rates['wide']['sector'] = get_rates(sec_indic)
            rates['base']['sector'] = round(get_growth(base_rate, self.sector['base_rate']['avg']), 4)

        return rates

    def estimate_company(self) -> None:
        self.data = network.download_data(self.ticker_str)

        self.sector_str = self.data[DataType.PROFILE.value]['sector']
        self.industry_str = self.data[DataType.PROFILE.value]['industry']
        if (self.sector_str != self.all_tickers[self.ticker_str]['sector'] or
            self.industry_str != self.all_tickers[self.ticker_str]['industry']) and not self.is_new_ticker:
            self.remove_ticker()

        self.prepare_data()
        self.upgrade_ticker_json()

        json.dump(self.ticker, open(self.ticker_path, 'wt', encoding='utf-8'))
        json.dump(self.industry, open(self.industry_path, 'wt', encoding='utf-8'))
        json.dump(self.sector, open(self.sector_path, 'wt', encoding='utf-8'))

        self.all_tickers[self.ticker_str] = {
            'version': self.version,
            'sector': self.sector_str,
            'industry': self.industry_str,
            'lastUpdate': self.ticker['lastUpdate']
        }
        if self.is_new_ticker:
            self.all_tickers['count'] = self.all_tickers['count'] + 1
        json.dump(self.all_tickers, open(f'{Company.data_path}all_tickers.json', 'wt', encoding='utf-8'))

    def upload_data(self) -> None:
        self.sector_str = self.all_tickers[self.ticker_str]['sector']
        self.industry_str = self.all_tickers[self.ticker_str]['industry']
        self.prepare_data()
        self.ticker = self.old_ticker
        self.industry = self.old_industry
        if (None in self.ticker['relative_rate']['base']) | (None in self.ticker['relative_rate']['wide']):
            self.ticker['relative_rate'] = self.get_relative_rate(self.ticker["base_rate"], self.ticker["indicators"])
            json.dump(self.ticker, open(self.ticker_path, 'wt', encoding='utf-8'))

    def is_time_to_update(self, sec_time: float) -> bool:
        last_update = time.gmtime(sec_time)
        last_report = time.strptime(network.get_last_report_data(self.ticker_str), '%Y-%m-%d')
        return True if last_report > last_update else False

    def get_company_data(self) -> (bool, bool):
        self.all_tickers = json.load(open(f'{Company.data_path}all_tickers.json', 'rt', encoding='utf-8'))
        if self.ticker_str in self.all_tickers:
            return False, self.is_time_to_update(self.all_tickers[self.ticker_str]['lastUpdate'])
        else:
            return True, True
