import asyncio
from datetime import datetime
import io
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
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
import matplotlib.pyplot as plt
import pandas as pd

# 🔑 ТОКЕН БЕРЕТСЯ ИЗ НАСТРОЕК RAILWAY (Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

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
                KeyboardButton(text="📈 График прогресса"),
                KeyboardButton(text="🎯 Челлендж дня"),
            ],
            [
                KeyboardButton(text="🗑️ Удалить матч"),
                KeyboardButton(text="🌍 Статистика сообщества"),
            ],
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
        f"Привет, **{message.from_user.first_name}**! ⚽🔥\n\n"
        "Твой личный футбольный трекер готов к работе. Фиксируй матчи, добавляй прошлые заслуги, "
        "выбирай позицию на поле и соревнуйся в топах!\n\n"
        "Выбирай нужное действие в меню ниже:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )


# --- ВЫБОР ПОЗИЦИИ НА ПОЛЕ ---
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
    await message.answer(
        "👤 **Выбери свою основную позицию на поле:**",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


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

    await callback.message.edit_text(
        f"✅ Позиция успешно обновлена: **{position}**!", parse_mode="Markdown"
    )
    await callback.answer()


# --- ДОБАВЛЕНИЕ ПРОШЛОЙ СТАТИСТИКИ ---
@dp.message(F.text == "📜 Добавить прошлые голы")
async def start_past_stats(message: types.Message, state: FSMContext):
    await state.set_state(PastStatsForm.waiting_for_past_goals)
    await message.answer(
        "📜 **Прошлые заслуги**\n\n"
        "Сколько всего голов ты забил **до того, как пришел в бота**? (Введите общую сумму цифрой):",
        parse_mode="Markdown",
    )


@dp.message(PastStatsForm.waiting_for_past_goals)
async def process_past_goals(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer(
            "⚠️ Пожалуйста, введи целое число (например: `150`):",
            parse_mode="Markdown",
        )
        return

    past_goals = int(message.text)
    await state.update_data(past_goals=past_goals)
    await state.set_state(PastStatsForm.waiting_for_past_matches)
    await message.answer(
        "👟 Отлично! А сколько примерно матчей ты сыграл до этого?"
    )


@dp.message(PastStatsForm.waiting_for_past_matches)
async def process_past_matches(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введи целое число матчей:")
        return

    past_matches = int(message.text)
    await state.update_data(past_matches=past_matches)
    await state.set_state(PastStatsForm.waiting_for_past_hours)
    await message.answer(
        "⏱️ И сколько примерно часов провел на поле в прошлых матчах? (например: `40`):"
    )


@dp.message(PastStatsForm.waiting_for_past_hours)
async def process_past_hours(message: types.Message, state: FSMContext):
    try:
        past_hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("⚠️ Введи корректное число часов:")
        return

    user_data = await state.get_data()
    past_goals = user_data["past_goals"]
    past_matches = user_data["past_matches"]
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
        (
            user_id,
            username,
            past_goals,
            past_matches,
            past_hours,
            past_goals,
            past_matches,
            past_hours,
            username,
        ),
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"✅ **Прошлые данные успешно сохранены!**\n\n"
        f"⚽ Прошлые голы: **{past_goals}**\n"
        f"👟 Прошлые матчи: **{past_matches}**\n"
        f"⏱️ Прошлое время: **{past_hours:.1f} ч.**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )


def get_user_rank(total_goals):
    if total_goals >= 300:
        return "👑 Легенда поля"
    elif total_goals >= 150:
        return "⭐ Звезда футбола"
    elif total_goals >= 70:
        return "🔥 Профессионал"
    elif total_goals >= 30:
        return "⚡ Уверенный игрок"
    elif total_goals >= 10:
        return "📈 Прогрессирующий"
    else:
        return "🌱 Новичок"


def check_achievements(user_id):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*), SUM(goals), MAX(goals), SUM(hours) FROM matches WHERE user_id = ?",
        (user_id,),
    )
    match_res = cursor.fetchone()
    cursor.execute(
        "SELECT past_goals, past_matches, past_hours FROM profiles WHERE user_id = ?",
        (user_id,),
    )
    profile_res = cursor.fetchone()
    conn.close()

    b_games, b_goals, b_max, b_hours = (
        match_res if match_res else (0, 0, 0, 0.0)
    )
    b_goals = b_goals if b_goals else 0
    b_max = b_max if b_max else 0
    b_hours = b_hours if b_hours else 0.0

    p_goals, p_matches, p_hours = (
        profile_res if profile_res else (0, 0, 0.0)
    )
    p_goals = p_goals if p_goals else 0
    p_matches = p_matches if p_matches else 0
    p_hours = p_hours if p_hours else 0.0

    total_games = b_games + p_matches
    total_goals = b_goals + p_goals
    total_hours = b_hours + p_hours

    unlocked = []
    if total_games >= 1:
        unlocked.append("👟 **Первый шаг** — Вход в систему")
    if total_goals >= 50:
        unlocked.append("🎯 **Снайпер** — Забито 50+ голов суммарно")
    if total_goals >= 200:
        unlocked.append("🏆 **Бомбардир** — Забито 200+ голов суммарно")
    if b_max >= 5:
        unlocked.append("🔥 **Хет-трик** — 5+ голов за один матч через бота")
    if total_hours >= 20:
        unlocked.append("⏱️ **Трудоголик** — Наиграно 20+ часов")
    return unlocked


# --- ЗАПИСЬ МАТЧА ---
@dp.message(F.text == "⚽ Записать матч")
async def start_add_game(message: types.Message, state: FSMContext):
    await state.set_state(GameForm.waiting_for_goals)
    await message.answer(
        "⚽ **Новый матч**\n\nСколько голов ты забил? Отправь цифру в чат:"
    )


@dp.message(GameForm.waiting_for_goals)
async def process_goals(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введи целое число:")
        return
    goals = int(message.text)
    await state.update_data(goals=goals)
    await state.set_state(GameForm.waiting_for_hours)
    await message.answer("⏱️ Сколько часов длился матч или тренировка?")


@dp.message(GameForm.waiting_for_hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("⚠️ Введи корректное число часов:")
        return

    user_data = await state.get_data()
    goals = user_data["goals"]
    today = datetime.now().strftime("%d.%m.%Y")
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
        f"✅ **Матч успешно сохранен!**\n📅 Дата: `{today}`\n⚽ Голы: **{goals}**\n⏱️ Время: **{hours} ч.**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )


# --- ДОСТИЖЕНИЯ ---
@dp.message(F.text == "🎖️ Мои достижения")
async def show_my_achievements(message: types.Message):
    user_id = message.from_user.id
    achievements = check_achievements(user_id)
    if not achievements:
        await message.answer(
            "🎖️ У тебя пока нет открытых достижений. Запиши матч!"
        )
        return
    text = "🎖️ **ТВОИ ДОСТИЖЕНИЯ:**\n\n"
    for ach in achievements:
        text += f"• {ach}\n"
    await message.answer(text, parse_mode="Markdown")


# --- ТАБЛИЦА ЛИДЕРОВ ---
@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Общий топ", callback_data="top_all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚽ Топ Нападающих", callback_data="top_Нападающий"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Топ Полузащитников", callback_data="top_Полузащитник"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛡️ Топ Защитников", callback_data="top_Защитник"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧤 Топ Вратарей", callback_data="top_Вратарь"
                )
            ],
        ]
    )
    await message.answer(
        "🏆 **ВЫБЕРИ КАТЕГОРИЮ РЕЙТИНГА:**",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("top_"))
async def show_top_by_position(callback: types.CallbackQuery):
    pos_filter = callback.data.split("_")[1]
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    query = """
        SELECT 
            p.user_id, 
            p.username, 
            p.position,
            COALESCE(p.past_goals, 0) + COALESCE(SUM(m.goals), 0) as total_goals,
            COALESCE(p.past_matches, 0) + COUNT(m.id) as total_matches
        FROM profiles p
        LEFT JOIN matches m ON p.user_id = m.user_id
    """

    if pos_filter != "all":
        query += " WHERE p.position = ?"
        query += " GROUP BY p.user_id ORDER BY total_goals DESC LIMIT 10"
        cursor.execute(query, (pos_filter,))
    else:
        query += " GROUP BY p.user_id ORDER BY total_goals DESC LIMIT 10"
        cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()

    if not rows or all(r[3] == 0 for r in rows):
        await callback.message.edit_text(
            "🏆 В этой категории пока нет игроков."
        )
        await callback.answer()
        return

    text = "🏆 **ТОП-10 ИГРОКОВ:**\n\n"
    for i, row in enumerate(rows):
        u_id, username, position, total_goals, total_matches = row
        display_name = (
            f"@{username}" if not username.startswith("Игрок") else username
        )
        text += f"{i+1}. **{display_name}** — ⚽ **{total_goals}** голов\n"

    await callback.message.edit_text(text, parse_mode="Markdown")
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
        await message.answer("❌ Нет матчей для удаления.")
        return

    keyboard_buttons = []
    for row in rows:
        match_id, date, goals, hours = row
        btn_text = f"❌ [{date}] Голов: {goals}"
        keyboard_buttons.append(
            [InlineKeyboardButton(text=btn_text, callback_data=f"del_{match_id}")]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(
        "🗑️ **Выбери матч для удаления:**",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("del_"))
async def process_delete_match(callback: types.CallbackQuery):
    match_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM matches WHERE id = ? AND user_id = ?",
        (match_id, user_id),
    )
    conn.commit()
    conn.close()
    await callback.message.edit_text("🗑️ Матч успешно удален!")
    await callback.answer()


# --- ЛИЧНАЯ СТАТИСТИКА ---
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
    match_data = cursor.fetchone()
    conn.close()

    position = prof[0] if prof and prof[0] else "Не указана"
    p_goals = prof[1] if prof and prof[1] else 0
    p_matches = prof[2] if prof and prof[2] else 0
    p_hours = prof[3] if prof and prof[3] else 0.0

    b_goals, b_hours, b_matches = (
        match_data if match_data else (0, 0.0, 0)
    )
    b_goals = b_goals if b_goals else 0
    b_hours = b_hours if b_hours else 0.0
    b_matches = b_matches if b_matches else 0

    total_goals = p_goals + b_goals
    total_matches = p_matches + b_matches
    total_hours = p_hours + b_hours
    current_rank = get_user_rank(total_goals)

    text = (
        f"📊 **ТВОЯ СТАТИСТИКА**\n\n"
        f"👤 Позиция: **{position}**\n"
        f"🎖️ Ранг: **{current_rank}**\n"
        f"👟 Всего игр: **{total_matches}**\n"
        f"⚽ Всего голов: **{total_goals}**\n"
        f"⏱️ Наиграно: **{total_hours:.1f} ч.**"
    )
    await message.answer(text, parse_mode="Markdown")


# --- СТАТИСТИКА СООБЩЕСТВА ---
@dp.message(F.text == "🌍 Статистика сообщества")
async def show_global_stats(message: types.Message):
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*), SUM(past_goals), SUM(past_matches), SUM(past_hours) FROM profiles"
    )
    p_count, p_g, p_m, p_h = cursor.fetchone()
    cursor.execute("SELECT COUNT(*), SUM(goals), SUM(hours) FROM matches")
    b_count, b_g, b_h = cursor.fetchone()
    conn.close()

    total_goals = (p_g or 0) + (b_g or 0)
    total_matches = (p_m or 0) + (b_count or 0)
    total_hours = (p_h or 0.0) + (b_h or 0.0)

    text = (
        f"🌍 **СТАТИСТИКА СООБЩЕСТВА**\n\n"
        f"⚽ Суммарно голов: **{total_goals}**\n"
        f"👟 Сыграно матчей: **{total_matches}**\n"
        f"⏱️ Суммарно часов: **{total_hours:.1f} ч.**"
    )
    await message.answer(text, parse_mode="Markdown")


# --- ГРАФИК ПРОГРЕССА ---
@dp.message(F.text == "📈 График прогресса")
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
        await message.answer("📈 Запиши хотя бы пару матчей через бота!")
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
    plt.title("Динамика результатов", fontsize=14, fontweight="bold")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await message.answer_photo(
        photo=photo, caption="📈 **Твой граф
