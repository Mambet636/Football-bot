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

# 🔑 ТОКЕН БЕРЕТСЯ АВТОМАТИЧЕСКИ ИЗ НАСТРОЕК RAILWAY (Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ SQLITE ---
def init_db():
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    # Таблица матчей
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

    # Таблица профилей пользователей (позиция и прошлый опыт)
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


# --- ДОБАВЛЕНИЕ ПРОШЛОЙ СТАТИСТИКИ (ДО БОТА) ---
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
        "⏱️ И сколько примерно часов провел на поле в прошлых матчах? (например: `40` или `50.5`):"
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
        f"⏱️ Прошлое время: **{past_hours:.1f} ч.**\n\n"
        "Теперь они учитываются в твоей общей статистике и топе!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )


# --- СИСТЕМА РАНГОВ ---
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


# --- ПРОВЕРКА ДОСТИЖЕНИЙ ---
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

    if total_hours >= 100:
        unlocked.append("🛡️ **Фанатик игры** — Наиграно 100+ часов")

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
        await message.answer(
            "⚠️ Введи целое число (например: `2`, `3`):", parse_mode="Markdown"
        )
        return

    goals = int(message.text)
    if goals > 50:
        await message.answer(
            "🚨 Невозможно забить больше 50 голов за матч. Повтори ввод:"
        )
        return
    if goals < 0:
        await message.answer("⚠️ Количество голов не может быть отрицательным.")
        return

    await state.update_data(goals=goals)
    await state.set_state(GameForm.waiting_for_hours)
    await message.answer(
        "⏱️ Сколько часов длился матч или тренировка? (например: `1.5`):"
    )


@dp.message(GameForm.waiting_for_hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("⚠️ Введи корректное число часов (например: `1.5`):")
        return

    if hours <= 0 or hours > 24:
        await message.answer("🚨 Время матча должно быть от 0.1 до 24 часов.")
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

    cursor.execute(
        "SELECT MAX(goals) FROM matches WHERE user_id = ?", (user_id,)
    )
    max_goals = cursor.fetchone()[0]
    conn.close()

    record_text = ""
    if goals == max_goals and goals > 0:
        record_text = (
            "\n\n🎉 **Отлично! Это твой лучший результат за матч через бота.** 🔥"
        )

    await state.clear()
    await message.answer(
        f"✅ **Матч успешно сохранен!**\n\n📅 Дата: `{today}`\n⚽ Голы: **{goals}**\n⏱️ Время: **{hours} ч.**{record_text}",
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
            "🎖️ У тебя пока нет открытых достижений. Запиши матч или добавь прошлую статистику!"
        )
        return

    text = "🎖️ **ТВОИ ДОСТИЖЕНИЯ:**\n\n"
    for ach in achievements:
        text += f"• {ach}\n"

    await message.answer(text, parse_mode="Markdown")


# --- ТАБЛИЦА ЛИДЕРОВ (ПО ПОЗИЦИЯМ) ---
@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Общий топ (Все позиции)",
                    callback_data="top_all",
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
        title_text = f"🏆 **ТОП-10 ПОЗИЦИЯ: {pos_filter.upper()}** 🏆"
    else:
        query += " GROUP BY p.user_id ORDER BY total_goals DESC LIMIT 10"
        cursor.execute(query)
        title_text = "🏆 **ОБЩИЙ ТОП-10 ИГРОКОВ СЕТИ** 🏆"

    rows = cursor.fetchall()
    conn.close()

    if not rows or all(r[3] == 0 for r in rows):
        await callback.message.edit_text(
            "🏆 В этой категории пока нет игроков с результатами."
        )
        await callback.answer()
        return

    text = f"{title_text}\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    keyboard_buttons = []
    for i, row in enumerate(rows):
        u_id, username, position, total_goals, total_matches = row
        display_name = (
            f"@{username}" if not username.startswith("Игрок") else username
        )
        medal = medals[i] if i < len(medals) else "⚽"
        pos_label = f"[{position}]" if position != "Не указана" else ""

        text += f"{medal} **{display_name}** {pos_label} — ⚽ **{total_goals}** голов *({total_matches} игр)*\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"⚔️ Дуэль с {display_name}", callback_data=f"duel_{u_id}"
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(
        text, reply_markup=keyboard, parse_mode="Markdown"
    )
    await callback.answer()


# --- ДУЭЛЬ СТАТИСТИКИ ---
@dp.callback_query(F.data.startswith("duel_"))
async def process_duel(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split("_")[1])
    my_user_id = callback.from_user.id

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    def get_full_user_stats(uid):
        cursor.execute(
            "SELECT username, position, past_goals, past_matches, past_hours FROM profiles WHERE user_id = ?",
            (uid,),
        )
        p = cursor.fetchone()
        cursor.execute(
            "SELECT SUM(goals), SUM(hours), COUNT(id) FROM matches WHERE user_id = ?",
            (uid,),
        )
        m = cursor.fetchone()
        return p, m

    t_profile, t_matches_db = get_full_user_stats(target_user_id)
    m_profile, m_matches_db = get_full_user_stats(my_user_id)
    conn.close()

    if not t_profile:
        await callback.answer("❌ Игрок не найден.", show_alert=True)
        return

    t_name, t_pos, t_pg, t_pm, t_ph = t_profile
    t_bg, t_bh, t_bm = (
        t_matches_db if t_matches_db else (0, 0.0, 0)
    )
    t_goals = t_pg + (t_bg if t_bg else 0)
    t_matches = t_pm + (t_bm if t_bm else 0)
    t_hours = t_ph + (t_bh if t_bh else 0.0)

    m_name, m_pos, m_pg, m_pm, m_ph = (
        m_profile if m_profile else ("Я", "Не указана", 0, 0, 0.0)
    )
    m_bg, m_bh, m_bm = (
        m_matches_db if m_matches_db else (0, 0.0, 0)
    )
    m_goals = m_pg + (m_bg if m_bg else 0)
    m_matches = m_pm + (m_bm if m_bm else 0)
    m_hours = m_ph + (m_bh if m_bh else 0.0)

    t_display = f"@{t_name}" if not t_name.startswith("Игрок") else t_name
    m_display = f"@{m_name}" if not m_name.startswith("Игрок") else m_name

    text = (
        f"⚔️ **СРАВНЕНИЕ СТАТИСТИКИ** ⚔️\n\n"
        f"👤 **Ты ({m_display})** VS 👤 **Соперник ({t_display})**\n\n"
        f"⚽ Голы: **{m_goals}** 🆚 **{t_goals}**\n"
        f"👟 Матчи: **{m_matches}** 🆚 **{t_matches}**\n"
        f"⏱️ Время: **{m_hours:.1f}ч** 🆚 **{t_hours:.1f}ч**\n\n"
    )

    if m_goals > t_goals:
        text += "🎉 Ты впереди по голям!"
    elif m_goals < t_goals:
        text += "💪 Соперник впереди по голям. Повод поднажать!"
    else:
        text += "🤝 Полное равенство!"

    await callback.message.answer(text, parse_mode="Markdown")
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
        await message.answer(
            "❌ Нет добавленных через бота матчей для удаления."
        )
        return

    keyboard_buttons = []
    for row in rows:
