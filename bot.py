import json
import sqlite3
from datetime import datetime
import requests
import time

# ========== НАСТРОЙКИ ==========
TOKEN = "8236443127:AAEAa2aN5bYfQV8coFnXLE2SFIfGNlswtmk"  # Замените на ваш токен!
DB_FILE = "finance_simple.db"


# ========== БАЗА ДАННЫХ ==========
def init_db():
    """Создаем простую базу данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            description TEXT,
            date TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных готова")


def save_expense(user_id, amount, category, description=""):
    """Сохраняем расход в базу"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        '''INSERT INTO expenses (user_id, amount, category, description, date) 
           VALUES (?, ?, ?, ?, ?)''',
        (user_id, amount, category, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )

    conn.commit()
    conn.close()
    return True


def get_user_expenses(user_id, limit=10):
    """Получаем расходы пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        '''SELECT amount, category, description, date 
           FROM expenses 
           WHERE user_id = ? 
           ORDER BY date DESC 
           LIMIT ?''',
        (user_id, limit)
    )

    expenses = cursor.fetchall()
    conn.close()
    return expenses


# ========== РАБОТА С TELEGRAM API ==========
def send_message(chat_id, text):
    """Отправляем сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=data)
        return response.json()
    except:
        return None


def get_updates(offset=None):
    """Получаем обновления от Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

    params = {"timeout": 30}
    if offset:
        params["offset"] = offset

    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except:
        return {"ok": False, "result": []}


# ========== ОБРАБОТКА КОМАНД ==========
def handle_command(user_id, chat_id, command, text):
    """Обрабатываем команды пользователя"""

    if command == "/start":
        message = (
            f"👋 Привет! Я бот для учета расходов.\n\n"
            f"Просто отправь мне:\n"
            f"<code>1500 еда обед в кафе</code>\n\n"
            f"Где:\n"
            f"• 1500 - сумма\n"
            f"• еда - категория\n"
            f"• обед в кафе - описание\n\n"
            f"Доступные команды:\n"
            f"/list - мои расходы\n"
            f"/help - помощь"
        )
        send_message(chat_id, message)

    elif command == "/help":
        message = (
            "📚 <b>Помощь по боту:</b>\n\n"
            "📝 <b>Добавить расход:</b>\n"
            "Просто отправь:\n"
            "<code>1500 еда обед</code>\n\n"
            "<b>Примеры:</b>\n"
            "<code>300 транспорт такси</code>\n"
            "<code>5000 аренда квартира</code>\n"
            "<code>1200 продукты</code>\n\n"
            "<b>Команды:</b>\n"
            "/start - начать\n"
            "/list - мои расходы\n"
            "/help - помощь"
        )
        send_message(chat_id, message)

    elif command == "/list":
        expenses = get_user_expenses(user_id, 10)

        if not expenses:
            send_message(chat_id, "📭 У вас еще нет расходов")
            return

        message = "📋 <b>Ваши расходы:</b>\n\n"
        total = 0

        for i, (amount, category, description, date_str) in enumerate(expenses, 1):
            total += amount
            date_formatted = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m")

            message += f"{i}. {date_formatted}: {amount:.2f} руб. - {category}"
            if description:
                message += f" ({description})"
            message += "\n"

        message += f"\n💰 <b>Всего:</b> {total:.2f} руб."
        send_message(chat_id, message)

    else:
        # Пытаемся обработать как расход
        handle_expense(user_id, chat_id, text)


def handle_expense(user_id, chat_id, text):
    """Обрабатываем ввод расхода"""
    parts = text.strip().split()

    if len(parts) < 2:
        send_message(chat_id, "❌ <b>Ошибка!</b> Нужно: СУММА КАТЕГОРИЯ\nПример: <code>1500 еда</code>")
        return

    # Проверяем сумму
    try:
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0:
            send_message(chat_id, "❌ Сумма должна быть больше 0")
            return
    except ValueError:
        send_message(chat_id, "❌ Первое значение должно быть числом (сумма)")
        return

    # Получаем категорию и описание
    category = parts[1]
    description = " ".join(parts[2:]) if len(parts) > 2 else ""

    # Сохраняем расход
    save_expense(user_id, amount, category, description)

    # Отправляем подтверждение
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    message = (
        f"✅ <b>Расход добавлен!</b>\n\n"
        f"💰 <b>Сумма:</b> {amount:.2f} руб.\n"
        f"📂 <b>Категория:</b> {category}\n"
    )

    if description:
        message += f"📝 <b>Описание:</b> {description}\n"

    message += f"📅 <b>Дата:</b> {now}"

    send_message(chat_id, message)


# ========== ГЛАВНЫЙ ЦИКЛ ==========
def main():
    """Главная функция бота"""
    print("=" * 50)
    print("🤖 ЗАПУСКАЕМ ПРОСТОЙ БОТ ДЛЯ УЧЕТА РАСХОДОВ")
    print("=" * 50)

    # Инициализируем базу данных
    init_db()

    # Проверяем токен
    if TOKEN == "ВАШ_ТОКЕН_ЗДЕСЬ":
        print("❌ ОШИБКА: Замените TOKEN на ваш токен бота!")
        print("Получите токен у @BotFather в Telegram")
        return

    print(f"✅ Токен: {TOKEN[:10]}...")
    print("✅ База данных готова")
    print("✅ Бот запущен! Ожидаем сообщения...")
    print("=" * 50)

    offset = None

    # Бесконечный цикл опроса
    while True:
        try:
            # Получаем обновления
            updates = get_updates(offset)

            if updates.get("ok"):
                for update in updates["result"]:
                    # Обновляем offset
                    offset = update["update_id"] + 1

                    # Проверяем есть ли сообщение
                    if "message" in update and "text" in update["message"]:
                        message = update["message"]
                        user_id = message["from"]["id"]
                        chat_id = message["chat"]["id"]
                        text = message["text"]

                        print(f"📨 Сообщение от {user_id}: {text}")

                        # Определяем команду
                        if text.startswith("/"):
                            command = text.split()[0]
                            handle_command(user_id, chat_id, command, text)
                        else:
                            # Обрабатываем как расход
                            handle_expense(user_id, chat_id, text)

            # Пауза между запросами
            time.sleep(1)

        except KeyboardInterrupt:
            print("\n👋 Останавливаем бота...")
            break
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()