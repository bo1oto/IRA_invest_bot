from logic import start_telegram_bot

if __name__ == '__main__':
    try:
        start_telegram_bot()
    except Exception as exc:
        with open('\\error.txt', 'wt') as file:
            file.write(str(exc))
