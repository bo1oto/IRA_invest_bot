import json
import time
from enum import Enum
from os.path import exists

from telegram.ext import MessageHandler, Filters, MessageFilter
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, \
    ReplyKeyboardMarkup, Update, ReplyKeyboardRemove, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, Dispatcher

import analyzer
import network


# Для каждого языка своя группа биндов (в будущем свой диспатчер наверное, хз()
# 0 группа - группа с командами и callback
class HandlerGroup(Enum):
    MAIN_MENU = 0
    CONFIG = 1
    REQUEST = 2
    ADMIN = 3


bot_version = 'v0.1'

orig_bot_token: str = '2117017621:AAEvDWDuwMXFoQleaLp8OqZkc5tk_QUf2IE'
test_bot_token: str = '2009741400:AAHYdzqM_3cX72EEWbAKsWDGg0AFruhS1z0'

admin_id: int = 1090869834
bot: Bot = Bot(token=orig_bot_token)
updater: Updater = Updater(bot=bot)
dispatcher: Dispatcher = updater.dispatcher
lang_dict: dict = {}
available_lang: dict = dict(en=u"\U0001F1EC" + u"\U0001F1E7",
                            ru=u"\U0001F1F7" + u"\U0001F1FA")
key_words: list = [
    ["О боте", "План", "Обратная", "Финансовая", "Графики", "Отчёт", "Смена", "Закрыть"],
    ["About", "Roadmap", "Feedback", "Financial", "Charts", "Report", "Change", "Close"]
]


# Service functions
def upload_dict() -> None:
    file_dict = open("\\Config/language.json", "rt", encoding="utf-8")
    global lang_dict
    lang_dict = json.load(file_dict)
    file_dict.close()

def no_context_message(update: Update, context: CallbackContext) -> None:
    update.message.reply_copy(update.effective_chat.id, update.message.message_id)


# Config functions
def update_config(user_id: int, lang: str = '', work_mode: int = -1, chart=(-1, True), report=("heh", -1, True),
                  dynamics: int = False) -> None:
    file_path = f'\\Config/users/{str(user_id)}.json'
    if exists(file_path):
        file_config = open(file_path, "rt")
        config = json.load(file_config)
        file_config.close()
        if lang:
            config["language"] = lang
        if work_mode != -1:
            config["work_mode"] = work_mode
        if chart[0] != -1:
            config['config']['chart'][chart[0]] = chart[1]
        if not report[0].__eq__("heh"):
            config['config']['report'][report[0]][report[1]] = report[2]
        if dynamics:
            config['config']['report']['dynamics'] = 1 if config['config']['report']['dynamics'] == 0 else 0
    else:
        # Задаём дефолтные настройки, уже три :)
        config = {
            'language': 'en',
            'work_mode': 0,
            'config': {
                'report': {
                    'finance': [
                        True,  # Revenue
                        True,  # Net income
                        True  # FCF
                    ],
                    'balance': [
                        True,  # Total Debt
                        False,  # Cash and equivalents
                        True  # Net Debt
                    ],
                    'rate': [
                        True,  # base_rate
                        False,  # relative_rate industry
                        True  # relative_rate sector
                    ],
                    'div': [
                        True,
                        False
                    ],
                    'dcf': False,
                    'dynamics': 0
                },
                'chart': [
                    True  # Base price chart
                ]
            }
        }

    file_config = open(file_path, "wt")
    json.dump(config, file_config)
    file_config.close()

def get_lang_code(user_id: int) -> str:
    file_path = f'\\Config/users/{str(user_id)}.json'
    if exists(file_path):
        file_config = open(file_path, "rt")
        config = json.load(file_config)
        file_config.close()
        return config["language"]
    else:
        # Если по какой-то причине конфиг пропал, создаём новый
        # + надо наверное уведомить и попросить заново настроить бота
        return "en"

def get_work_mode(user_id: int) -> int:
    file_path = f'\\Config/users/{str(user_id)}.json'
    if exists(file_path):
        file_config = open(file_path, "rt")
        config = json.load(file_config)
        file_config.close()
        return config["work_mode"]
    else:
        # Если по какой-то причине конфиг пропал, создаём новый
        # + надо наверное уведомить и попросить заново настроить бота
        return 0

def get_config(user_id: int) -> dict:
    file_path = f'\\Config/users/{str(user_id)}.json'
    if exists(file_path):
        file_config = open(file_path, "rt")
        config = json.load(file_config)
        file_config.close()
        return config["config"]
    else:
        # Если по какой-то причине конфиг пропал, создаём новый
        # + надо наверное уведомить и попросить заново настроить бота
        return {
            'language': 'en',
            'work_mode': 0,
            'config': {
                'report': {
                    'finance': [
                        True,  # Revenue
                        True,  # Net income
                        True  # FCF
                    ],
                    'balance': [
                        True,  # Total Debt
                        False,  # Cash and equivalents
                        True  # Net Debt
                    ],
                    'rate': [
                        True,  # base_rate
                        False,  # relative_rate industry
                        True  # relative_rate sector
                    ],
                    'div': [
                        True,
                        False
                    ],
                    'dcf': False,
                    'dynamics': 0
                },
                'chart': [
                    True  # Base price chart
                ]
            }
        }


# Main functions
def start(update: Update, context: CallbackContext) -> None:
    if update.effective_user.language_code in available_lang:
        update_config(update.effective_user.id, update.effective_user.language_code)
        send_help(update, context)
    else:
        select_lang(update, context)

def send_help(update: Update, context: CallbackContext) -> None:
    update.effective_chat.send_message(lang_dict[get_lang_code(update.effective_user.id)]["help"])

def close_keyboard(update: Update, context: CallbackContext) -> None:
    update.effective_chat.send_message(u"\U0000267B", reply_markup=ReplyKeyboardRemove())

def close_inline_keyboard(update: Update, context: CallbackContext) -> None:
    update.callback_query.edit_message_text(lang_dict[get_lang_code(update.effective_user.id)]["settings"]["closed"])

# Admin :)
def clear(update: Update, context: CallbackContext) -> None:
    update.message.reply_markdown_v2("Cleared", reply_markup=ReplyKeyboardRemove())


# Work modes
def select_work_mode(update: Update, context: CallbackContext) -> None:
    # По идее, у каждой надо содержать строку, описывающую режим после нажатия кнопки
    keyboard = []
    _id = update.effective_user.id
    lang_code = get_lang_code(_id)
    modes_list = list(lang_dict[lang_code]["work_mode"]["modes"])
    for i, mode in enumerate(modes_list):
        keyboard.append([InlineKeyboardButton(mode, callback_data='m_' + str(i))])
    keyboard.append([InlineKeyboardButton(lang_dict[lang_code]["settings"]["close"], callback_data='c_e')])
    update.message.reply_markdown_v2(lang_dict[lang_code]["work_mode"]["select"] + modes_list[get_work_mode(_id)],
                                     reply_markup=InlineKeyboardMarkup(keyboard))

def work_mode_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    lang_code = get_lang_code(update.effective_user.id)
    update_config(update.effective_user.id, work_mode=int(query.data[-1]))
    query.edit_message_text(lang_dict[lang_code]["work_mode"]["selected"] +
                            lang_dict[lang_code]["work_mode"]["modes"][query.data[-1]])


# Settings
def settings_menu(update: Update, context: CallbackContext) -> None:
    keyboard = []
    lang_code = get_lang_code(update.effective_user.id)
    for word in lang_dict[lang_code]["set_menu"]["cmd"]:
        keyboard.append([KeyboardButton(word)])
    update.effective_chat.send_message(lang_dict[lang_code]["set_menu"]["text"],
                                       reply_markup=ReplyKeyboardMarkup(keyboard))

def select_lang(update: Update, context: CallbackContext) -> None:
    keyboard = []
    for code in available_lang.keys():
        keyboard.append([InlineKeyboardButton(available_lang[code], callback_data='l_' + code)])
    update.message.reply_markdown_v2(
        lang_dict[get_lang_code(update.effective_user.id)]["settings"]["language"]["select"],
        reply_markup=InlineKeyboardMarkup(keyboard))

def lang_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    q_data = query.data[2:]
    update_config(update.effective_user.id, lang=q_data)
    query.edit_message_text(lang_dict[q_data]["settings"]["language"]["selected"])
    close_keyboard(update, context)

# report
def generate_report_config_keyboard(update: Update, type_num: int) -> tuple[str, InlineKeyboardMarkup]:
    report_types = [
        "finance",
        "balance",
        "div",
        "rate"
    ]
    if type_num == len(report_types):  # Обновляем, если в конце списка типов
        type_num = 0
    lang_code = get_lang_code(update.effective_user.id)
    report_dict = lang_dict[lang_code]["settings"]["report"]
    config = get_config(update.effective_user.id)["report"]

    keyboard = [[InlineKeyboardButton(report_dict[report_types[type_num]]["name"],
                                      callback_data='c_r' + 't' + str(type_num))]
                ]
    for conf, text, i in zip(config[report_types[type_num]],
                             report_dict[report_types[type_num]]["data"],
                             range(len(config))):
        smile = u"\U00002705" if conf else u"\U0000274C"
        keyboard.append([InlineKeyboardButton(f'{text} {smile}', callback_data='c_r' + str(i + 1) + str(type_num))])
    keyboard.append([InlineKeyboardButton(
        report_dict["dynamics"]["base_line"] +
        report_dict["dynamics"]["data"][config["dynamics"]],
        callback_data='c_rd' + str(type_num))])
    keyboard.append([InlineKeyboardButton(lang_dict[lang_code]["settings"]["close"], callback_data='c_e')])
    return report_dict["name"], InlineKeyboardMarkup(keyboard)

def select_report_config(update: Update, context: CallbackContext) -> None:
    title, keyboard = generate_report_config_keyboard(update, 0)
    update.message.reply_markdown_v2(title, reply_markup=keyboard)

def report_config_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data[3] == 't':
        title, keyboard = generate_report_config_keyboard(update, int(query.data[-1]) + 1)
        query.edit_message_text(title, reply_markup=keyboard)
        return
    elif query.data[3] == 'd':
        update_config(update.effective_user.id, dynamics=True)
        title, keyboard = generate_report_config_keyboard(update, int(query.data[-1]))
        query.edit_message_text(title, reply_markup=keyboard)
        return

    option_num = int(query.data[3])
    keyboard = query.message.reply_markup
    text = keyboard.inline_keyboard[option_num][0].text
    state = True if text[-1] == u"\U0000274C" else False
    keyboard.inline_keyboard[option_num][0].text = text.replace(
        text[-1],
        u"\U00002705" if text[-1] == u"\U0000274C" else u"\U0000274C"
    )
    query.edit_message_text(query.message.text, reply_markup=keyboard)

    report_tags = [
        "finance",
        "balance",
        "div",
        "rate"
    ]
    type_num = int(keyboard.inline_keyboard[option_num][0].callback_data.__str__()[4])
    update_config(update.effective_user.id, report=(report_tags[type_num], option_num - 1, state))

# chart
def select_chart_config(update: Update, context: CallbackContext) -> None:
    keyboard = []
    lang_code = get_lang_code(update.effective_user.id)
    config: list = get_config(update.effective_user.id)["chart"]
    for conf, text, i in zip(config, lang_dict[lang_code]["settings"]["chart"]["data"], range(len(config))):
        smile = u"\U00002705" if conf else u"\U0000274C"
        keyboard.append([InlineKeyboardButton(f'{text} {smile}', callback_data='c_c' + str(i))])
    keyboard.append([InlineKeyboardButton(lang_dict[lang_code]["settings"]["close"], callback_data='c_e')])
    update.message.reply_markdown_v2(
        lang_dict[lang_code]["settings"]["chart"]["name"],
        reply_markup=InlineKeyboardMarkup(keyboard))

def chart_config_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    option_num = int(query.data[3])
    keyboard = query.message.reply_markup
    text = keyboard.inline_keyboard[option_num][0].text
    state = True if text[-1] == u"\U0000274C" else False
    keyboard.inline_keyboard[option_num][0].text = text.replace(
        text[-1],
        u"\U00002705" if text[-1] == u"\U0000274C" else u"\U0000274C"
    )
    query.edit_message_text(query.message.text, reply_markup=keyboard)
    update_config(update.effective_user.id, chart=(option_num, state))

# Info
def info_menu(update: Update, context: CallbackContext) -> None:
    keyboard = []
    lang_code = get_lang_code(update.effective_user.id)
    for word in lang_dict[lang_code]["info_menu"]["cmd"]:
        keyboard.append([KeyboardButton(word)])
    update.effective_chat.send_message(lang_dict[lang_code]["info_menu"]["text"],
                                       reply_markup=ReplyKeyboardMarkup(keyboard))

def info_handler(update: Update, context: CallbackContext) -> None:
    lang_code = get_lang_code(update.effective_user.id)
    code_num = 0 if lang_code == "ru" else 1
    text = update.message.text
    if key_words[code_num][0] in text:
        update.effective_chat.send_message(lang_dict[lang_code]["info"]["about"])
    elif key_words[code_num][1] in text:
        update.effective_chat.send_message(lang_dict[lang_code]["info"]["plan"])
    elif key_words[code_num][2] in text:
        update.effective_chat.send_message(lang_dict[lang_code]["info"]["feedback"])
    elif key_words[code_num][3] in text:
        update.message.reply_markdown_v2(lang_dict[lang_code]["info"]["money"], disable_web_page_preview=True)
    else:
        update.effective_chat.send_message("error?!")


# Ticker analisys
class TickerFilter(MessageFilter):
    def filter(self, message: Message) -> bool:
        for char in message.text:
            char_code = ord(char)
            if (char_code >= 65) & (char_code <= 90) | (char_code == 32):
                pass
            else:
                for lang_words in key_words:
                    for word in lang_words:
                        if word in message.text:
                            return False
                bad_ticker_format(message.chat, message.from_user.id, message.text)
                return False
        if network.check_ticker(message.text):
            return True
        else:
            ticker_not_found(message.chat, message.from_user.id)
            return False

def ticker_not_found(chat, user_id: int) -> None:
    chat.send_message(lang_dict[get_lang_code(user_id)]["bad_ticker"]["not_found"])

def bad_ticker_format(chat, user_id: int, text: str) -> None:
    lang_code = get_lang_code(user_id)
    work_mode = get_work_mode(user_id)
    chat.send_message(lang_dict[lang_code]["bad_ticker"]["text"] +
                      lang_dict[lang_code]["bad_ticker"]["formats"][work_mode])
    log_file = open("\\log.txt", "at", encoding="utf-8")
    log_file.write(f'{time.strftime("%Y-%m-%d %X")}; user: {user_id}; text: {text};\n')
    log_file.close()

def determine_req_type(update: Update, context: CallbackContext) -> None:
    analyze_ticker(update.effective_chat, update.effective_user.id, update.message.text)

def analyze_ticker(chat, user_id: int, ticker: str) -> None:
    config = get_config(user_id)
    company = analyzer.Company(ticker, bot_version, config["report"]["dynamics"])
    report = company.generate_report(get_config(user_id), lang_dict[get_lang_code(user_id)]["report"])
    # Отчёт может быть и без графика, или же с массивом графиков
    if config['chart']['data'][0]:
        plot_path = company.generate_chart()
        chat.send_photo(open(plot_path, 'rb'), caption=report)
    else:
        chat.send_message(report)
    """
    chat.send_media_group(media=[
        telegram.InputMediaPhoto(open(plot_path, 'rb'), caption=report),
        telegram.InputMediaPhoto(open(plot_path, 'rb'))
    ])
    """

# Base
def bind_handlers() -> None:
    dispatcher.add_handler(CallbackQueryHandler(report_config_selected, pattern='c_r'), 0)
    dispatcher.add_handler(CallbackQueryHandler(chart_config_selected, pattern='c_c'), 0)
    dispatcher.add_handler(CallbackQueryHandler(close_inline_keyboard, pattern='c_e'), 0)
    dispatcher.add_handler(CallbackQueryHandler(lang_selected, pattern='l_'), 0)
    dispatcher.add_handler(CallbackQueryHandler(work_mode_selected, pattern='m_'), 0)

    dispatcher.add_handler(CommandHandler("settings", settings_menu), 0)
    dispatcher.add_handler(CommandHandler("work_mode", select_work_mode), 0)
    dispatcher.add_handler(CommandHandler("info", info_menu), 0)
    dispatcher.add_handler(CommandHandler("help", send_help), 0)
    dispatcher.add_handler(CommandHandler("start", start), 0)

    dispatcher.add_handler(MessageHandler(Filters.user(admin_id) & Filters.text("/clear"), clear), 0)
    dispatcher.add_handler(MessageHandler(Filters.text & TickerFilter(), determine_req_type), 0)

    for i, code in enumerate(available_lang):
        func_list = [select_chart_config, select_report_config, select_lang]
        for j, func in zip(range(4, 7), func_list):
            dispatcher.add_handler(MessageHandler(Filters.regex(key_words[i][j]), func), i + 1)
        dispatcher.add_handler(MessageHandler(
            Filters.regex(key_words[i][0]) | Filters.regex(key_words[i][1]) |
            Filters.regex(key_words[i][2]) | Filters.regex(key_words[i][3]),
            info_handler), i + 1)
        dispatcher.add_handler(MessageHandler(Filters.regex(key_words[i][-1]), close_keyboard), i + 1)

    dispatcher.add_handler(MessageHandler(~Filters.text, no_context_message), dispatcher.handlers.__len__())

def start_telegram_bot() -> None:
    upload_dict()
    bind_handlers()
    updater.start_webhook(listen='0.0.0.0',
                          port=443,
                          url_path=orig_bot_token,
                          key='\\tg-key.key',
                          cert='\\tg-cert.pem',
                          webhook_url='13.51.244.137:443/' + orig_bot_token)