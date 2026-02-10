import json
import sqlite3
from datetime import datetime
import requests
import time

TOKEN = "8236443127:AAEAa2aN5bYfQV8coFnXLE2SFIfGNlswtmk"
DB_FILE = "finance_simple.db"

# Категории для кнопок
CATEGORIES = [
    "🍔 Еда",
    "👕 Одежда",
    "🏠 Коммуналка",
    "🎮 Развлечения",
    "🚗 Транспорт",
    "💊 Здоровье",
    "📱 Техника",
    "💼 Прочее"
]

# Состояния пользователей (храним в памяти)
user_states = {}


def init_db():
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


def get_stats(user_id):
    """Получить статистику за месяц"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Общая сумма за месяц
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= date('now', '-30 days')",
        (user_id,)
    )
    total = cursor.fetchone()[0] or 0

    # По категориям
    cursor.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND date >= date('now', '-30 days') GROUP BY category",
        (user_id,)
    )
    categories = cursor.fetchall()
    conn.close()

    return total, categories


def send_message(chat_id, text, keyboard=None):
    """Отправка сообщения с клавиатурой"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if keyboard:
        data["reply_markup"] = json.dumps({
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": False
        })

    try:
        response = requests.post(url, json=data)
        return response.json()
    except:
        return None


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except:
        return {"ok": False, "result": []}


# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    """Главное меню"""
    return [
        ["➕ Добавить расход"],
        ["📋 Мои расходы", "📊 Статистика"],
        ["❓ Помощь"]
    ]


def get_categories_keyboard():
    """Клавиатура с категориями"""
    keyboard = []

    # Разбиваем категории на ряды по 2 кнопки
    for i in range(0, len(CATEGORIES), 2):
        row = []
        if i < len(CATEGORIES):
            row.append(CATEGORIES[i])
        if i + 1 < len(CATEGORIES):
            row.append(CATEGORIES[i + 1])
        keyboard.append(row)

    # Добавляем кнопку отмены
    keyboard.append(["❌ Отмена"])
    return keyboard


def get_cancel_keyboard():
    """Клавиатура только с отменой"""
    return [["❌ Отмена"]]


def get_description_keyboard():
    """Клавиатура для описания"""
    return [["📝 Без описания", "❌ Отмена"]]


# ========== ОБРАБОТЧИКИ КОМАНД ==========
def handle_start(user_id, chat_id, first_name):
    """Обработка команды /start"""
    message = (
        f"👋 Привет, {first_name}!\n\n"
        f"Я бот для учета расходов с удобными кнопками!\n\n"
        f"<b>Как пользоваться:</b>\n"
        f"1. Нажми '➕ Добавить расход'\n"
        f"2. Введи сумму\n"
        f"3. Выбери категорию из кнопок\n"
        f"4. (Необязательно) Добавь описание\n\n"
        f"Используй кнопки ниже ⬇️"
    )
    send_message(chat_id, message, get_main_keyboard())


def handle_help(chat_id):
    """Обработка команды /help"""
    message = (
        "📚 <b>Помощь по боту:</b>\n\n"
        "<b>Как добавить расход:</b>\n"
        "1. Нажми '➕ Добавить расход'\n"
        "2. Введи сумму (например: 1500)\n"
        "3. Выбери категорию из кнопок\n"
        "4. (Необязательно) Добавь описание\n\n"
        "<b>Категории:</b>\n"
        "🍔 Еда - продукты, кафе, рестораны\n"
        "👕 Одежда - одежда, обувь, аксессуары\n"
        "🏠 Коммуналка - ЖКХ, интернет, связь\n"
        "🎮 Развлечения - кино, игры, хобби\n"
        "🚗 Транспорт - бензин, такси, проезд\n"
        "💊 Здоровье - лекарства, врачи, спорт\n"
        "📱 Техника - гаджеты, электроника\n"
        "💼 Прочее - все остальное\n\n"
        "<b>Команды:</b>\n"
        "/start - начать работу\n"
        "/help - помощь"
    )
    send_message(chat_id, message, get_main_keyboard())


def handle_add_expense(user_id, chat_id):
    """Начало добавления расхода"""
    user_states[user_id] = {"state": "waiting_amount"}
    send_message(
        chat_id,
        "💸 <b>Введите сумму расхода:</b>\n\n"
        "Например: <code>1500</code> или <code>99.99</code>",
        get_cancel_keyboard()
    )


def handle_list_expenses(user_id, chat_id):
    """Показать расходы пользователя"""
    expenses = get_user_expenses(user_id, 10)

    if not expenses:
        send_message(chat_id, "📭 У вас еще нет расходов", get_main_keyboard())
        return

    message = "📋 <b>Ваши расходы:</b>\n\n"
    total = 0

    for i, (amount, category, description, date_str) in enumerate(expenses, 1):
        total += amount
        date_formatted = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m")

        message += f"{i}. {date_formatted}: <b>{amount:.2f} руб.</b> - {category}"
        if description:
            message += f"\n   📝 {description}"
        message += "\n\n"

    message += f"💰 <b>Итого за последние 10 записей:</b> {total:.2f} руб."
    send_message(chat_id, message, get_main_keyboard())


def handle_stats(user_id, chat_id):
    """Показать статистику"""
    total, categories = get_stats(user_id)

    if total == 0:
        send_message(chat_id, "📊 У вас еще нет расходов за последний месяц", get_main_keyboard())
        return

    message = "📊 <b>Статистика за месяц:</b>\n\n"
    message += f"💰 <b>Всего потрачено:</b> {total:.2f} руб.\n\n"

    if categories:
        message += "📈 <b>По категориям:</b>\n"
        for category, amount in categories:
            percent = (amount / total * 100) if total > 0 else 0
            message += f"• {category}: {amount:.2f} руб. ({percent:.1f}%)\n"

    send_message(chat_id, message, get_main_keyboard())


def process_amount(user_id, chat_id, amount_text):
    """Обработка введенной суммы"""
    try:
        amount = float(amount_text.replace(',', '.'))

        if amount <= 0:
            send_message(chat_id, "❌ Сумма должна быть больше 0. Попробуйте снова:", get_cancel_keyboard())
            return

        # Сохраняем сумму и меняем состояние
        user_states[user_id] = {
            "state": "waiting_category",
            "amount": amount
        }

        send_message(
            chat_id,
            f"💰 <b>Сумма:</b> {amount:.2f} руб.\n\n"
            f"📂 <b>Выберите категорию:</b>",
            get_categories_keyboard()
        )

    except ValueError:
        send_message(
            chat_id,
            "❌ Неверный формат!\n"
            "Введите число, например: <code>1500</code> или <code>99.99</code>",
            get_cancel_keyboard()
        )


def process_category(user_id, chat_id, category):
    """Обработка выбранной категории"""
    if category not in CATEGORIES and category != "➕ Другая категория":
        send_message(chat_id, "❌ Выберите категорию из списка кнопок:", get_categories_keyboard())
        return

    if category == "➕ Другая категория":
        user_states[user_id]["state"] = "waiting_custom_category"
        send_message(chat_id, "✏️ <b>Введите свою категорию:</b>\n\nНапример: <code>Кредит</code>, <code>Ремонт</code>",
                     get_cancel_keyboard())
        return

    # Сохраняем категорию
    user_states[user_id]["category"] = category
    user_states[user_id]["state"] = "waiting_description"

    send_message(
        chat_id,
        f"💰 <b>Сумма:</b> {user_states[user_id]['amount']:.2f} руб.\n"
        f"📂 <b>Категория:</b> {category}\n\n"
        f"✏️ <b>Введите описание (или нажмите '📝 Без описания'):</b>",
        get_description_keyboard()
    )


def process_custom_category(user_id, chat_id, custom_category):
    """Обработка пользовательской категории"""
    if len(custom_category) > 50:
        send_message(chat_id, "❌ Категория слишком длинная. Максимум 50 символов.", get_cancel_keyboard())
        return

    # Сохраняем пользовательскую категорию
    user_states[user_id]["category"] = custom_category
    user_states[user_id]["state"] = "waiting_description"

    send_message(
        chat_id,
        f"💰 <b>Сумма:</b> {user_states[user_id]['amount']:.2f} руб.\n"
        f"📂 <b>Категория:</b> {custom_category}\n\n"
        f"✏️ <b>Введите описание (или нажмите '📝 Без описания'):</b>",
        get_description_keyboard()
    )


def process_description(user_id, chat_id, description):
    """Обработка описания и сохранение расхода"""
    if description == "📝 Без описания":
        description = ""

    # Получаем данные из состояния
    state_data = user_states[user_id]
    amount = state_data["amount"]
    category = state_data["category"]

    # Сохраняем расход
    save_expense(user_id, amount, category, description)

    # Формируем сообщение
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    message = (
        f"✅ <b>Расход успешно добавлен!</b>\n\n"
        f"💰 <b>Сумма:</b> {amount:.2f} руб.\n"
        f"📂 <b>Категория:</b> {category}\n"
    )

    if description:
        message += f"📝 <b>Описание:</b> {description}\n"

    message += f"📅 <b>Дата:</b> {now}"

    # Отправляем сообщение и очищаем состояние
    send_message(chat_id, message, get_main_keyboard())
    del user_states[user_id]


# ========== ГЛАВНЫЙ ОБРАБОТЧИК ==========
def handle_message(user_id, chat_id, text, first_name):
    """Обработка всех сообщений"""

    # Проверяем главные кнопки
    if text == "➕ Добавить расход":
        handle_add_expense(user_id, chat_id)

    elif text == "📋 Мои расходы":
        handle_list_expenses(user_id, chat_id)

    elif text == "📊 Статистика":
        handle_stats(user_id, chat_id)

    elif text == "❓ Помощь":
        handle_help(chat_id)

    elif text == "❌ Отмена":
        if user_id in user_states:
            del user_states[user_id]
        send_message(chat_id, "❌ Операция отменена", get_main_keyboard())

    # Проверяем состояние пользователя
    elif user_id in user_states:
        state = user_states[user_id]["state"]

        if state == "waiting_amount":
            process_amount(user_id, chat_id, text)

        elif state == "waiting_category":
            process_category(user_id, chat_id, text)

        elif state == "waiting_custom_category":
            process_custom_category(user_id, chat_id, text)

        elif state == "waiting_description":
            process_description(user_id, chat_id, text)

    # Обработка команд
    elif text.startswith("/"):
        if text == "/start":
            handle_start(user_id, chat_id, first_name)
        elif text == "/help":
            handle_help(chat_id)
        elif text == "/list":
            handle_list_expenses(user_id, chat_id)
        elif text == "/stats":
            handle_stats(user_id, chat_id)
        elif text == "/add":
            handle_add_expense(user_id, chat_id)
        else:
            send_message(chat_id, "Неизвестная команда. Используйте кнопки меню.", get_main_keyboard())

    # Если это не команда и не кнопка, пробуем обработать как старый формат расхода
    else:
        # Старый формат: "1500 еда обед"
        parts = text.strip().split()

        if len(parts) >= 2:
            try:
                amount = float(parts[0].replace(',', '.'))
                if amount > 0:
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

                    send_message(chat_id, message, get_main_keyboard())
                else:
                    send_message(chat_id, "❌ Сумма должна быть больше 0", get_main_keyboard())
            except ValueError:
                send_message(chat_id, "❌ Неверный формат! Используйте кнопку '➕ Добавить расход'", get_main_keyboard())
        else:
            send_message(chat_id, "Используйте кнопки меню для работы с ботом.", get_main_keyboard())


# ========== ГЛАВНЫЙ ЦИКЛ ==========
def main():
    print("=" * 50)
    print("🤖 ЗАПУСКАЕМ БОТ С КНОПКАМИ ДЛЯ УЧЕТА РАСХОДОВ")
    print("=" * 50)

    init_db()

    print(f"✅ Токен: {TOKEN[:10]}...")
    print("✅ База данных готова")
    print("✅ Категории настроены")
    print("✅ Бот запущен! Ожидаем сообщения...")
    print("=" * 50)

    offset = None

    while True:
        try:
            updates = get_updates(offset)

            if updates.get("ok"):
                for update in updates["result"]:
                    offset = update["update_id"] + 1

                    if "message" in update and "text" in update["message"]:
                        message = update["message"]
                        user_id = message["from"]["id"]
                        chat_id = message["chat"]["id"]
                        text = message["text"]
                        first_name = message["from"].get("first_name", "друг")

                        print(f"📨 Сообщение от {user_id} ({first_name}): {text}")

                        # Обрабатываем сообщение
                        handle_message(user_id, chat_id, text, first_name)

            time.sleep(1)

        except KeyboardInterrupt:
            print("\n👋 Останавливаем бота...")
            break
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()