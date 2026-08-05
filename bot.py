asyncio
import datetime
import logging
import os
import random
import sqlite3
import sys

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
import pandas as pd

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            position TEXT,
            past_goals INTEGER DEFAULT 0,
            past_matches INTEGER DEFAULT 0,
            past_hours REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()


init_db()


class GameForm(StatesGroup):
    waiting_for_goals = State()
    waiting_for_hours = State()


class PastStatsForm(StatesGroup):
    waiting_for_past_goals = State()
    waiting_for_past_matches = State()
    waiting_for_past_hours = State()


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚽ Записать матч"),
                KeyboardButton(text="📜 Добавить прошлые голы"),
            ],
            [
                KeyboardButton(text="📊 Моя статистика"),
                KeyboardButton(text="👤 Выбрать позицию"),
            ],
            [
                KeyboardButton(text="🏆 Таблица лидеров"),
                KeyboardButton(text="🎖️ Мои достижения"),
            ],
            [
                KeyboardButton(text="🎯 Челлендж дня"),
                KeyboardButton(text="🗑️ Удалить матч"),
            ],
            [KeyboardButton(text="🌍 Статистика сообщества")],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = (
        message.from_user.username
        or message.from_user.first_name
        or "Игрок"
    )

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO profiles (user_id, username, position) VALUES (?, ?, ?)",
        (user_id, username, "Не указана"),
    )
    conn.commit()
    conn.close()

    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Твой личный футбольный трекер готов к работе. Фиксируй матчи, добавляй прошлые заслуги, "
        "выбирай позицию на поле и соревнуйся в топах!\n\n"
        "Выбирай нужное действие в меню ниже:",
        reply_markup=get_main_keyboard(),
    )


@dp.message(F.text == "👤 Выбрать позицию")
async def select_position(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚽ Нападающий", callback_data="pos_Нападающий"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Полузащитник", callback_data="pos_Полузащитник"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛡️ Защитник", callback_data="pos_Защитник"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧤 Вратарь", callback_data="pos_Вратарь"
                )
            ],
        ]
    )
    await message.answer("Выбери свою основную позицию на поле:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("pos_"))
async def process_position(callback: types.CallbackQuery):
    position = callback.data.split("_")[1]
    user_id = callback.from_user.id

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE profiles SET position = ? WHERE user_id = ?",
        (position, user_id),
    )
    conn.commit()
    conn.close()

    await callback.message.edit_text(f"Позиция успешно обновлена: {position}!")
    await callback.answer()


@dp.message(F.text == "📜 Добавить прошлые голы")
async def start_past_stats(message: types.Message, state: FSMContext):
    await state.set_state(PastStatsForm.waiting_for_past_goals)
    await message.answer(
        "Сколько всего голов ты забил до того, как пришел в бота? (Введите общую сумму цифрой):"
    )


@dp.message(PastStatsForm.waiting_for_past_goals)
async def process_past_goals(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи целое число (например: 150):")
        return
    await state.update_data(past_goals=int(message.text))
    await state.set_state(PastStatsForm.waiting_for_past_matches)
    await message.answer("А сколько примерно матчей ты сыграл до этого?")


@dp.message(PastStatsForm.waiting_for_past_matches)
async def process_past_matches(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число матчей:")
        return
    await state.update_data(past_matches=int(message.text))
    await state.set_state(PastStatsForm.waiting_for_past_hours)
    await message.answer("И сколько примерно часов провел на поле в прошлых матчах?")


@dp.message(PastStatsForm.waiting_for_past_hours)
async def process_past_hours(message: types.Message, state: FSMContext):
    try:
        past_hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи корректное число часов:")
        return

    data = await state.get_data()
    pg, pm = data["past_goals"], data["past_matches"]
    user_id = message.from_user.id
    username = (
        message.from_user.username
        or message.from_user.first_name
        or "Игрок"
    )

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO profiles (user_id, username, position, past_goals, past_matches, past_hours) 
        VALUES (?, ?, 'Не указана', ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
        past_goals = ?, past_matches = ?, past_hours = ?, username = ?
    """,
        (user_id, username, pg, pm, past_hours, pg, pm, past_hours, username),
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"Прошлые данные сохранены!\nГолы: {pg}\nМатчи: {pm}\nЧасы: {past_hours:.1f}",
        reply_markup=get_main_keyboard(),
    )


def get_user_rank(g):
    if g >= 300:
        return "Легенда поля"
    elif g >= 150:
        return "Звезда футбола"
    elif g >= 70:
        return "Профессионал"
    elif g >= 30:
        return "Уверенный игрок"
    elif g >= 10:
        return "Прогрессирующий"
    else:
        return "Новичок"


@dp.message(F.text == "⚽ Записать матч")
async def start_add_game(message: types.Message, state: FSMContext):
    await state.set_state(GameForm.waiting_for_goals)
    await message.answer("Сколько голов ты забил сегодня?")


@dp.message(GameForm.waiting_for_goals)
async def process_goals(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число:")
        return
    await state.update_data(goals=int(message.text))
    await state.set_state(GameForm.waiting_for_hours)
    await message.answer("Сколько часов длился матч или тренировка?")


@dp.message(GameForm.waiting_for_hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи корректное число часов:")
        return

    data = await state.get_data()
    goals = data["goals"]
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    user_id = message.from_user.id
    username = (
        message.from_user.username
        or message.from_user.first_name
        or "Игрок"
    )

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO matches (user_id, username, date, goals, hours) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, today, goals, hours),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO profiles (user_id, username, position) VALUES (?, ?, ?)",
        (user_id, username, "Не указана"),
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"Матч успешно сохранен!\nДата: {today}\nГолы: {goals}\nВремя: {hours} ч.",
        reply_markup=get_main_keyboard(),
    )


@dp.message(F.text == "📊 Моя статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT position, past_goals, past_matches, past_hours FROM profiles WHERE user_id = ?",
        (user_id,),
    )
    prof = cursor.fetchone()
    cursor.execute(
        "SELECT SUM(goals), SUM(hours), COUNT(id) FROM matches WHERE user_id = ?",
        (user_id,),
    )
    m_data = cursor.fetchone()
    conn.close()

    pos = prof[0] if prof and prof[0] else "Не указана"
    pg, pm, ph = (
        (prof[1], prof[2], prof[3]) if prof else (0, 0, 0.0)
    )
    bg, bh, bm = (
        (m_data[0], m_data[1], m_data[2]) if m_data else (0, 0.0, 0)
    )

    total_g = (pg or 0) + (bg or 0)
    total_m = (pm or 0) + (bm or 0)
    total_h = (ph or 0.0) + (bh or 0.0)
    rank = get_user_rank(total_g)

    await message.answer(
        f"ТВОЯ СТАТИСТИКА:\n\n"
        f"Позиция: {pos}\n"
        f"Ранг: {rank}\n"
        f"Всего игр: {total_m}\n"
        f"Всего голов: {total_g}\n"
        f"Наиграно: {total_h:.1f} ч."
    )


@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.username, 
               COALESCE(p.past_goals, 0) + COALESCE(SUM(m.goals), 0) as tg
        FROM profiles p
        LEFT JOIN matches m ON p.user_id = m.user_id
        GROUP BY p.user_id ORDER BY tg DESC LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Пока нет игроков в топе.")
        return

    text = "ТОП-10 ИГРОКОВ:\n\n"
    for i, r in enumerate(rows):
        text += f"{i+1}. {r[0]} — {r[1]} голов\n"
    await message.answer(text)


@dp.message(F.text == "🌍 Статистика сообщества")
async def show_global(message: types.Message):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT SUM(past_goals), SUM(past_matches), SUM(past_hours) FROM profiles"
    )
    pg, pm, ph = cursor.fetchone()
    cursor.execute("SELECT SUM(goals), COUNT(id), SUM(hours) FROM matches")
    bg, bm, bh = cursor.fetchone()
    conn.close()

    tg = (pg or 0) + (bg or 0)
    tm = (pm or 0) + (bm or 0)
    th = (ph or 0.0) + (bh or 0.0)

    await message.answer(
        f"СТАТИСТИКА СООБЩЕСТВА:\n\n"
        f"Всего голов: {tg}\n"
        f"Всего матчей: {tm}\n"
        f"Всего часов: {th:.1f}"
    )


@dp.message(F.text == "🎯 Челлендж дня")
async def challenge(message: types.Message):
    ex = [
        "Сделай 50 передач в стену правой ногой",
        "Сделай 50 передач в стену левой ногой",
        "Сделай 20 рывков по 30 метров",
    ]
    await message.answer(f"Челлендж на сегодня:\n\n{random.choice(ex)}")


@dp.message(F.text == "🗑️ Удалить матч")
async def del_match(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, goals FROM matches WHERE user_id = ? ORDER BY id DESC LIMIT 5",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Нет матчей для удаления.")
        return

    btns = [
        [
            InlineKeyboardButton(
                text=f"Удалить матч от {r[1]} (голов: {r[2]})",
                callback_data=f"del_{r[0]}",
            )
        ]
        for r in rows
    ]
    await message.answer(
        "Выбери матч для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
    )


@dp.callback_query(F.data.startswith("del_"))
async def remove_match(callback: types.CallbackQuery):
    m_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM matches WHERE id = ? AND user_id = ?",
        (m_id, callback.from_user.id),
    )
    conn.commit()
    conn.close()
    await callback.message.edit_text("Матч удален!")
    await callback.answer()


async def main():
    print("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
