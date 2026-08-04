import asyncio
from datetime import datetime
import io
import logging
import random
import sqlite3

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
import matplotlib.pyplot as plt
import pandas as pd

# 🔑 ТОКЕН ТВОЕГО TELEGRAM БОТА
BOT_TOKEN = "8236796974:AAGCq-RiXnh-Ui95Hm3xay-VpDje0k8X66s"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ SQLITE ---
def init_db():
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            date TEXT,
            goals INTEGER,
            hours REAL
        )
    """)
    conn.commit()
    conn.close()


init_db()


class GameForm(StatesGroup):
    waiting_for_goals = State()
    waiting_for_hours = State()


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚽ Записать матч"),
                KeyboardButton(text="🗑️ Удалить матч"),
            ],
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="📜 История"),
            ],
            [
                KeyboardButton(text="🏆 Таблица лидеров"),
                KeyboardButton(text="🎖️ Мои достижения"),
            ],
            [
                KeyboardButton(text="📈 График"),
                KeyboardButton(text="🎯 Случайный челлендж"),
            ],
            [KeyboardButton(text="🌍 Общая статистика")],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}.\n"
        "Футбольный бот готов к работе. Выберите нужное действие в меню ниже.",
        reply_markup=get_main_keyboard(),
    )


# --- СИСТЕМА РАНГОВ ---
def get_user_rank(total_goals):
    if total_goals >= 200:
        return "Легенда"
    elif total_goals >= 100:
        return "Элитный бомбардир"
    elif total_goals >= 50:
        return "Профессионал"
    elif total_goals >= 20:
        return "Уверенный игрок"
    elif total_goals >= 5:
        return "Любитель"
    else:
        return "Новичок"


# --- ПРОВЕРКА ДОСТИЖЕНИЙ ---
def check_achievements(user_id):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*), SUM(goals), MAX(goals), SUM(hours) FROM matches WHERE user_id = ?",
        (user_id,),
    )
    res = cursor.fetchone()
    conn.close()

    if not res or res[0] == 0:
        return []

    total_games, total_goals, max_goals, total_hours = res
    total_goals = total_goals if total_goals else 0
    max_goals = max_goals if max_goals else 0
    total_hours = total_hours if total_hours else 0

    unlocked = []

    if total_games >= 1:
        unlocked.append("Первый шаг — записан первый матч")

    if total_goals >= 50:
        unlocked.append("Снайпер — забито 50 голов суммарно")

    if total_goals >= 200:
        unlocked.append("Бомбардир — забито 200 голов суммарно")

    if max_goals >= 5:
        unlocked.append("Хет-трик — 5 и более голов за один матч")

    if max_goals >= 10:
        unlocked.append("Рекордсмен — 10 и более голов за один матч")

    if total_hours >= 10:
        unlocked.append("Активный — суммарно наиграно 10 часов")

    if total_hours >= 50:
        unlocked.append("Преданный делу — суммарно наиграно 50 часов")

    if total_games >= 20:
        unlocked.append("Регулярность — сыграно 20 матчей")

    return unlocked


# --- ЗАПИСЬ МАТЧА ---
@dp.message(F.text == "⚽ Записать матч")
async def start_add_game(message: types.Message, state: FSMContext):
    await state.set_state(GameForm.waiting_for_goals)
    await message.answer("Сколько голов вы забили в этом матче? Введите число:")


@dp.message(GameForm.waiting_for_goals)
async def process_goals(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите целое число (например: 2, 3):")
        return

    goals = int(message.text)

    if goals > 50:
        await message.answer(
            "Значение слишком велико. Максимальное количество голов за матч — 50. Повторите ввод:"
        )
        return

    if goals < 0:
        await message.answer("Количество голов не может быть отрицательным.")
        return

    await state.update_data(goals=goals)
    await state.set_state(GameForm.waiting_for_hours)
    await message.answer(
        "Сколько часов длился матч или тренировка? (например: 1, 1.5, 2):"
    )


@dp.message(GameForm.waiting_for_hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректное число часов (например: 1.5):")
        return

    if hours <= 0 or hours > 24:
        await message.answer(
            "Время матча должно быть от 0.1 до 24 часов. Повторите ввод:"
        )
        return

    user_data = await state.get_data()
    goals = user_data["goals"]
    today = datetime.now().strftime("%d.%m.%Y")
    user_id = message.from_user.id
    username = (
        message.from_user.username
        or message.from_user.first_name
        or "Пользователь"
    )

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO matches (user_id, username, date, goals, hours) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, today, goals, hours),
    )
    conn.commit()

    cursor.execute(
        "SELECT MAX(goals) FROM matches WHERE user_id = ?", (user_id,)
    )
    max_goals = cursor.fetchone()[0]
    conn.close()

    record_text = ""
    if goals == max_goals and goals > 0:
        record_text = (
            "\n\nПоздравляем, это ваш лучший результат по голам за матч."
        )

    await state.clear()
    await message.answer(
        f"Матч успешно сохранен.\n📅 Дата: {today}\n⚽ Голы: {goals}\n⏱️ Время: {hours} ч.{record_text}",
        reply_markup=get_main_keyboard(),
    )


# --- ДОСТИЖЕНИЯ ---
@dp.message(F.text == "🎖️ Мои достижения")
async def show_my_achievements(message: types.Message):
    user_id = message.from_user.id
    achievements = check_achievements(user_id)

    if not achievements:
        await message.answer(
            "У вас пока нет разблокированных достижений. Запишите свой первый матч."
        )
        return

    text = "Полученные достижения:\n\n"
    for ach in achievements:
        text += f"- {ach}\n"

    await message.answer(text)


# --- ТАБЛИЦА ЛИДЕРОВ ---
@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, SUM(goals) as total_goals, COUNT(id) as total_matches 
        FROM matches 
        GROUP BY user_id 
        ORDER BY total_goals DESC 
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Таблица лидеров пока пуста.")
        return

    text = (
        "Таблица лидеров\n"
        "Выберите игрока в списке ниже для сравнения статистики:\n\n"
    )
    positions = ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

    keyboard_buttons = []
    for i, row in enumerate(rows):
        u_id, username, total_goals, total_matches = row
        display_name = (
            f"@{username}"
            if not username.startswith("Пользователь")
            else username
        )
        pos = positions[i] if i < len(positions) else f"{i+1}."

        text += f"{pos} {display_name} — {total_goals} голов ({total_matches} игр)\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"Сравнить с {display_name}", callback_data=f"duel_{u_id}"
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard)


# --- СРАВНЕНИЕ (ДУЭЛЬ СТАТИСТИКИ) ---
@dp.callback_query(F.data.startswith("duel_"))
async def process_duel(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split("_")[1])
    my_user_id = callback.from_user.id

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT username, SUM(goals), SUM(hours), COUNT(id) FROM matches WHERE"
        " user_id = ?",
        (target_user_id,),
    )
    target_data = cursor.fetchone()

    cursor.execute(
        "SELECT username, SUM(goals), SUM(hours), COUNT(id) FROM matches WHERE"
        " user_id = ?",
        (my_user_id,),
    )
    my_data = cursor.fetchone()
    conn.close()

    if not target_data or target_data[1] is None:
        await callback.answer(
            "Данные выбранного пользователя не найдены.", show_alert=True
        )
        return

    t_name, t_goals, t_hours, t_matches = target_data
    m_name, m_goals, m_hours, m_matches = my_data

    t_goals = t_goals if t_goals else 0
    t_hours = t_hours if t_hours else 0
    t_matches = t_matches if t_matches else 0

    m_goals = m_goals if m_goals else 0
    m_hours = m_hours if m_hours else 0
    m_matches = m_matches if m_matches else 0

    t_display = f"@{t_name}" if not t_name.startswith("Пользователь") else t_name
    m_display = f"@{m_name}" if not m_name.startswith("Пользователь") else m_name

    text = (
        f"Сравнение статистики\n\n"
        f"Вы ({m_display}) / Соперник ({t_display})\n\n"
        f"- Голы: {m_goals} / {t_goals}\n"
        f"- Матчи: {m_matches} / {t_matches}\n"
        f"- Наиграно часов: {m_hours:.1f} ч. / {t_hours:.1f} ч.\n\n"
    )

    if m_goals > t_goals:
        text += "Вы опережаете соперника по количеству забитых голов."
    elif m_goals < t_goals:
        text += "Соперник опережает вас по количеству забитых голов."
    else:
        text += "Показатели по забитым голам равны."

    await callback.message.answer(text)
    await callback.answer()


# --- УДАЛЕНИЕ МАТЧА ---
@dp.message(F.text == "🗑️ Удалить матч")
async def select_match_to_delete(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, goals, hours FROM matches WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("У вас нет сохраненных матчей для удаления.")
        return

    keyboard_buttons = []
    for row in rows:
        match_id, date, goals, hours = row
        btn_text = f"[{date}] Голов: {goals} | Время: {hours}ч"
        keyboard_buttons.append(
            [InlineKeyboardButton(text=btn_text, callback_data=f"del_{match_id}")]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer("Выберите матч для удаления:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("del_"))
async def process_delete_match(callback: types.CallbackQuery):
    match_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, goals, hours FROM matches WHERE id = ? AND user_id = ?",
        (match_id, user_id),
    )
    match = cursor.fetchone()

    if match:
        date, goals, hours = match
        cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_text(
            f"Матч удален:\nДата: {date} — Голы: {goals} | Время: {hours} ч."
        )
    else:
        conn.close()
        await callback.message.edit_text(
            "Матч не найден или уже был удален ранее."
        )

    await callback.answer()


# --- ЛИЧНАЯ СТАТИСТИКА ---
@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT goals, hours FROM matches WHERE user_id = ?", (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "Статистика пуста. Запишите хотя бы один матч, чтобы увидеть данные."
        )
        return

    total_games = len(rows)
    total_goals = sum(row[0] for row in rows)
    total_hours = sum(row[1] for row in rows)
    avg_goals = total_goals / total_games
    max_goals = max(row[0] for row in rows)
    current_rank = get_user_rank(total_goals)

    text = (
        "Личная статистика:\n\n"
        f"- Текущий ранг: {current_rank}\n"
        f"- Всего игр: {total_games}\n"
        f"- Всего голов: {total_goals}\n"
        f"- Наиграно часов: {total_hours:.1f} ч.\n"
        f"- В среднем за игру: {avg_goals:.1f} гола\n"
        f"- Рекорд голов за матч: {max_goals}"
    )
    await message.answer(text)


# --- ОБЩАЯ СТАТИСТИКА ---
@dp.message(F.text == "🌍 Общая статистика")
async def show_global_stats(message: types.Message):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), SUM(goals), SUM(hours) FROM matches")
    total_games, total_goals, total_hours = cursor.fetchone()

    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM matches")
    total_players = cursor.fetchone()[0]
    conn.close()

    if not total_games or total_games == 0:
        await message.answer("Пока нет записей от пользователей.")
        return

    total_hours = total_hours if total_hours else 0
    total_goals = total_goals if total_goals else 0
    avg_global_goals = total_goals / total_games if total_games > 0 else 0

    text = (
        "Общая статистика системы:\n\n"
        f"- Всего игроков: {total_players}\n"
        f"- Сыграно матчей: {total_games}\n"
        f"- Забито голов суммарно: {total_goals}\n"
        f"- Суммарно наиграно часов: {total_hours:.1f} ч.\n"
        f"- Средняя результативность: {avg_global_goals:.1f} гола за игру"
    )
    await message.answer(text)


# --- ИСТОРИЯ МАТЧЕЙ ---
@dp.message(F.text == "📜 История")
async def show_history(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, goals, hours FROM matches WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("История матчей пуста.")
        return

    history_text = "Последние матчи:\n\n"
    for i, row in enumerate(rows, 1):
        history_text += f"{i}. {row[0]} — Голы: {row[1]} | Время: {row[2]} ч.\n"

    await message.answer(history_text)


# --- ГРАФИК ---
@dp.message(F.text == "📈 График")
async def show_chart(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    df = pd.read_sql_query(
        "SELECT date, goals FROM matches WHERE user_id = ?",
        conn,
        params=(user_id,),
    )
    conn.close()

    if df.empty:
        await message.answer(
            "Недостаточно данных для построения графика. Запишите больше матчей."
        )
        return

    plt.figure(figsize=(8, 4))
    plt.plot(
        range(len(df)),
        df["goals"],
        marker="o",
        color="#2ecc71",
        linewidth=2,
        markersize=8,
    )
    plt.title("Динамика результативности", fontsize=14, fontweight="bold")
    plt.xlabel("Матчи (по порядку)", fontsize=10)
    plt.ylabel("Голы", fontsize=10)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await message.answer_photo(
        photo=photo, caption="График изменения результатов по матчам."
    )


# --- ГЕНЕРАТОР ЧЕЛЛЕНДЖЕЙ ---
@dp.message(F.text == "🎯 Случайный челлендж")
async def daily_challenge(message: types.Message):
    actions = [
        "Выполните",
        "Сделайте",
        "Отработайте",
        "Набейте",
        "Пробейте",
        "Добейтесь серии из",
    ]
    counts = ["30", "50", "70", "100", "150", "10 точных", "15 мощных"]
    exercises = [
        "передач в стенку правой ногой без остановки мяча",
        "передач в стенку левой ногой с акцентом на точность",
        "челночных рывков по 30 метров с минимальным отдыхом",
        "ударов внешней стороной стопы по воротам",
        "ударов слёта с линии штрафной площади",
        "приемов мяча грудью с последующим ударом",
        "разворотов с мячом против условного соперника",
        "финтов с резким изменением направления движения",
        "жонглирования мячом попеременно бедрами и стопами",
        "ведения мяча змейкой между фишками на время",
    ]
    extras = [
        "на время (установите таймер 2 минуты).",
        "без потери контроля над мячом.",
        "с добавлением ускорения в конце каждого подхода.",
        "в высоком темпе.",
        "чередуя слабую и сильную ногу.",
    ]

    challenge_text = (
        f"Рекомендуемое упражнение на сегодня:\n\n"
        f"{random.choice(actions)} {random.choice(counts)} {random.choice(exercises)} {random.choice(extras)}"
    )

    await message.answer(challenge_text)


async def main():
    print("Бот запущен и работает в штатном режиме.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
