import json
import sqlite3
from datetime import datetime
import requests
import time

# ========== НАСТРОЙКИ БОТА ==========
TOKEN = "8236443127:AAEAa2aN5bYfQV8coFnXLE2SFIfGNlswtmk"  # Токен бота от @BotFather
DB_FILE = "finance_simple.db"  # Имя файла базы данных SQLite

# Список предустановленных категорий для быстрого выбора (эмодзи добавляют наглядности)
CATEGORIES = [
    "🍔 Еда",  # Продукты, кафе, рестораны
    "👕 Одежда",  # Одежда, обувь, аксессуары
    "🏠 Коммуналка",  # ЖКХ, интернет, связь, аренда
    "🎮 Развлечения",  # Кино, игры, хобби, подписки
    "🚗 Транспорт",  # Бензин, такси, общественный транспорт
    "💊 Здоровье",  # Лекарства, врачи, спортзал
    "📱 Техника",  # Гаджеты, электроника, ремонт
    "💼 Прочее"  # Всё остальное
]

# Хранилище состояний пользователей в оперативной памяти
# Ключ - ID пользователя, значение - словарь с данными состояния
# Пример: { user_id: {"state": "waiting_amount", "amount": 1500, "category": "Еда"} }
user_states = {}


def init_db():
    """Инициализация базы данных SQLite.
    Создает таблицу expenses, если она еще не существует."""
    conn = sqlite3.connect(DB_FILE)  # Подключаемся к БД (файл создастся автоматически)
    cursor = conn.cursor()  # Создаем курсор для выполнения запросов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Уникальный ID записи
            user_id INTEGER,                       -- ID пользователя в Telegram
            amount REAL,                           -- Сумма расхода
            category TEXT,                        -- Категория расхода
            description TEXT,                     -- Описание (необязательно)
            date TEXT                             -- Дата и время в формате "YYYY-MM-DD HH:MM:SS"
        )
    ''')
    conn.commit()  # Сохраняем изменения
    conn.close()  # Закрываем соединение
    print("✅ База данных готова")


def save_expense(user_id, amount, category, description=""):
    """Сохраняет расход в базу данных.

    Args:
        user_id: ID пользователя Telegram
        amount: Сумма расхода
        category: Категория расхода
        description: Описание (по умолчанию пустая строка)

    Returns:
        bool: True при успешном сохранении
    """
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
    """Получает последние расходы пользователя.

    Args:
        user_id: ID пользователя
        limit: Количество записей для вывода (по умолчанию 10)

    Returns:
        list: Список кортежей с данными расходов (amount, category, description, date)
    """
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
    expenses = cursor.fetchall()  # Получаем все найденные записи
    conn.close()
    return expenses


def get_stats(user_id):
    """Получить статистику расходов за последние 30 дней.

    Args:
        user_id: ID пользователя

    Returns:
        tuple: (общая сумма за месяц, список расходов по категориям)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Общая сумма за последние 30 дней
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= date('now', '-30 days')",
        (user_id,)
    )
    total = cursor.fetchone()[0] or 0  # Если None (нет расходов), возвращаем 0

    # Суммы по каждой категории за последние 30 дней
    cursor.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND date >= date('now', '-30 days') GROUP BY category",
        (user_id,)
    )
    categories = cursor.fetchall()
    conn.close()

    return total, categories


def send_message(chat_id, text, keyboard=None):
    """Отправка сообщения в Telegram с поддержкой клавиатур.

    Args:
        chat_id: ID чата в Telegram
        text: Текст сообщения (поддерживает HTML разметку)
        keyboard: Клавиатура в формате списка кнопок (опционально)

    Returns:
        dict: Ответ от Telegram API или None при ошибке
    """
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"  # URL метода sendMessage

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"  # Включаем поддержку HTML тегов
    }

    if keyboard:
        # Преобразуем нашу клавиатуру в формат, понятный Telegram API
        data["reply_markup"] = json.dumps({
            "keyboard": keyboard,  # Массив кнопок
            "resize_keyboard": True,  # Автоматически подгонять размер
            "one_time_keyboard": False  # Не скрывать клавиатуру после нажатия
        })

    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")
        return None


def get_updates(offset=None):
    """Получение новых сообщений от Telegram API.

    Args:
        offset: ID последнего обработанного сообщения + 1

    Returns:
        dict: Ответ от Telegram API с массивом новых сообщений
    """
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}  # Длинный polling (30 секунд)
    if offset:
        params["offset"] = offset  # Не получать старые сообщения

    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        print(f"Ошибка получения обновлений: {e}")
        return {"ok": False, "result": []}


# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    """Главная клавиатура с основными действиями."""
    return [
        ["➕ Добавить расход"],  # Кнопка добавления
        ["📋 Мои расходы", "📊 Статистика"],  # Две кнопки в ряду
        ["❓ Помощь"]  # Кнопка помощи
    ]


def get_categories_keyboard():
    """Клавиатура с категориями для выбора."""
    keyboard = []

    # Разбиваем список категорий на пары для удобного отображения
    for i in range(0, len(CATEGORIES), 2):
        row = []
        if i < len(CATEGORIES):
            row.append(CATEGORIES[i])
        if i + 1 < len(CATEGORIES):
            row.append(CATEGORIES[i + 1])
        keyboard.append(row)

    # Добавляем кнопку отмены в отдельном ряду
    keyboard.append(["❌ Отмена"])
    return keyboard


def get_cancel_keyboard():
    """Клавиатура только с кнопкой отмены (для прерывания операций)."""
    return [["❌ Отмена"]]


def get_description_keyboard():
    """Клавиатура для этапа ввода описания."""
    return [["📝 Без описания", "❌ Отмена"]]


# ========== ОБРАБОТЧИКИ КОМАНД ==========
def handle_start(user_id, chat_id, first_name):
    """Обработка команды /start - приветствие и инструкция."""
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
    """Обработка команды /help - подробная справка по боту."""
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
    """Начало процесса добавления расхода.
    Переводит пользователя в состояние ожидания ввода суммы."""
    user_states[user_id] = {"state": "waiting_amount"}  # Устанавливаем состояние
    send_message(
        chat_id,
        "💸 <b>Введите сумму расхода:</b>\n\n"
        "Например: <code>1500</code> или <code>99.99</code>",
        get_cancel_keyboard()  # Даем возможность отменить операцию
    )


def handle_list_expenses(user_id, chat_id):
    """Показать последние 10 расходов пользователя."""
    expenses = get_user_expenses(user_id, 10)

    if not expenses:
        send_message(chat_id, "📭 У вас еще нет расходов", get_main_keyboard())
        return

    message = "📋 <b>Ваши расходы:</b>\n\n"
    total = 0

    for i, (amount, category, description, date_str) in enumerate(expenses, 1):
        total += amount
        # Преобразуем дату из БД в удобный формат
        date_formatted = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m")

        message += f"{i}. {date_formatted}: <b>{amount:.2f} руб.</b> - {category}"
        if description:  # Если есть описание, добавляем его
            message += f"\n   📝 {description}"
        message += "\n\n"

    message += f"💰 <b>Итого за последние 10 записей:</b> {total:.2f} руб."
    send_message(chat_id, message, get_main_keyboard())


def handle_stats(user_id, chat_id):
    """Показать статистику расходов за месяц."""
    total, categories = get_stats(user_id)

    if total == 0:
        send_message(chat_id, "📊 У вас еще нет расходов за последний месяц", get_main_keyboard())
        return

    message = "📊 <b>Статистика за месяц:</b>\n\n"
    message += f"💰 <b>Всего потрачено:</b> {total:.2f} руб.\n\n"

    if categories:
        message += "📈 <b>По категориям:</b>\n"
        for category, amount in categories:
            percent = (amount / total * 100) if total > 0 else 0  # Вычисляем процент
            message += f"• {category}: {amount:.2f} руб. ({percent:.1f}%)\n"

    send_message(chat_id, message, get_main_keyboard())


def process_amount(user_id, chat_id, amount_text):
    """Обработка введенной пользователем суммы.

    Проверяет корректность формата, сохраняет сумму и переводит
    пользователя в состояние выбора категории.
    """
    try:
        # Заменяем запятую на точку для корректного преобразования в число
        amount = float(amount_text.replace(',', '.'))

        if amount <= 0:
            send_message(chat_id, "❌ Сумма должна быть больше 0. Попробуйте снова:", get_cancel_keyboard())
            return

        # Сохраняем сумму и меняем состояние пользователя
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
    """Обработка выбранной категории.

    Сохраняет категорию и переводит пользователя в состояние ввода описания.
    """
    if category not in CATEGORIES and category != "➕ Другая категория":
        send_message(chat_id, "❌ Выберите категорию из списка кнопок:", get_categories_keyboard())
        return

    # Обработка пользовательской категории
    if category == "➕ Другая категория":
        user_states[user_id]["state"] = "waiting_custom_category"
        send_message(chat_id, "✏️ <b>Введите свою категорию:</b>\n\nНапример: <code>Кредит</code>, <code>Ремонт</code>",
                     get_cancel_keyboard())
        return

    # Сохраняем выбранную категорию
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
    """Обработка пользовательской категории (своя категория).

    Проверяет длину и сохраняет пользовательскую категорию.
    """
    if len(custom_category) > 50:  # Ограничиваем длину
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
    """Обработка описания и финальное сохранение расхода.

    Сохраняет все данные в БД и завершает процесс добавления расхода.
    """
    if description == "📝 Без описания":
        description = ""  # Пустое описание

    # Получаем все сохраненные данные из состояния
    state_data = user_states[user_id]
    amount = state_data["amount"]
    category = state_data["category"]

    # Сохраняем расход в базу данных
    save_expense(user_id, amount, category, description)

    # Формируем сообщение с подтверждением
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    message = (
        f"✅ <b>Расход успешно добавлен!</b>\n\n"
        f"💰 <b>Сумма:</b> {amount:.2f} руб.\n"
        f"📂 <b>Категория:</b> {category}\n"
    )

    if description:
        message += f"📝 <b>Описание:</b> {description}\n"

    message += f"📅 <b>Дата:</b> {now}"

    # Отправляем подтверждение и очищаем состояние пользователя
    send_message(chat_id, message, get_main_keyboard())
    del user_states[user_id]  # Удаляем состояние, процесс завершен


# ========== ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ==========
def handle_message(user_id, chat_id, text, first_name):
    """Главный маршрутизатор сообщений.

    Определяет тип сообщения (команда, кнопка, текст) и вызывает
    соответствующий обработчик.
    """
    # === ОБРАБОТКА КНОПОК ГЛАВНОГО МЕНЮ ===
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
            del user_states[user_id]  # Очищаем состояние
        send_message(chat_id, "❌ Операция отменена", get_main_keyboard())

    # === ОБРАБОТКА СОСТОЯНИЙ (ДИАЛОГ ДОБАВЛЕНИЯ РАСХОДА) ===
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

    # === ОБРАБОТКА СТАНДАРТНЫХ КОМАНД ===
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

    # === ОБРАТНАЯ СОВМЕСТИМОСТЬ (СТАРЫЙ ФОРМАТ) ===
    else:
        # Проверяем, не пытается ли пользователь ввести расход в старом формате "1500 еда обед"
        parts = text.strip().split()

        if len(parts) >= 2:
            try:
                amount = float(parts[0].replace(',', '.'))
                if amount > 0:
                    category = parts[1]
                    description = " ".join(parts[2:]) if len(parts) > 2 else ""

                    # Сохраняем расход напрямую (без состояний)
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


# ========== ГЛАВНЫЙ ЦИКЛ БОТА ==========
def main():
    """Основная функция запуска бота.

    Инициализирует БД, запускает цикл получения обновлений от Telegram
    и обрабатывает входящие сообщения.
    """
    # Выводим информацию о запуске
    print("=" * 50)
    print("🤖 ЗАПУСКАЕМ БОТ С КНОПКАМИ ДЛЯ УЧЕТА РАСХОДОВ")
    print("=" * 50)

    # Инициализируем базу данных
    init_db()

    print(f"✅ Токен: {TOKEN[:10]}...")
    print("✅ База данных готова")
    print("✅ Категории настроены")
    print("✅ Бот запущен! Ожидаем сообщения...")
    print("=" * 50)

    # Переменная для хранения ID последнего обработанного сообщения
    offset = None

    # Бесконечный цикл получения и обработки сообщений
    while True:
        try:
            # Получаем новые сообщения от Telegram
            updates = get_updates(offset)

            if updates.get("ok"):  # Если запрос успешен
                for update in updates["result"]:
                    # Обновляем offset, чтобы не получать это сообщение снова
                    offset = update["update_id"] + 1

                    # Проверяем, что это текстовое сообщение
                    if "message" in update and "text" in update["message"]:
                        message = update["message"]
                        user_id = message["from"]["id"]  # ID пользователя
                        chat_id = message["chat"]["id"]  # ID чата
                        text = message["text"]  # Текст сообщения
                        first_name = message["from"].get("first_name", "друг")  # Имя пользователя

                        # Логируем полученное сообщение
                        print(f"📨 Сообщение от {user_id} ({first_name}): {text}")

                        # Обрабатываем сообщение
                        handle_message(user_id, chat_id, text, first_name)

            # Небольшая пауза, чтобы не нагружать процессор
            time.sleep(1)

        except KeyboardInterrupt:
            # Обработка Ctrl+C для graceful shutdown
            print("\n👋 Останавливаем бота...")
            break
        except Exception as e:
            # Обработка любых других ошибок
            print(f"⚠️ Ошибка: {e}")
            time.sleep(5)  # Пауза перед повторной попыткой


# Точка входа в программу
if __name__ == "__main__":
    main()