import asyncio
from datetime import datetime
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

BOT_TOKEN = os.getenv("8236796974:AAHLCK-e8-9YpYrWZUEaWlW_e2WWddn6kSo")

# Впиши сюда свой Telegram ID цифрами (например: 123456789)
ADMIN_ID = 0

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
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            conceded INTEGER DEFAULT 0,
            hours REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            position TEXT,
            past_goals INTEGER DEFAULT 0,
            past_assists INTEGER DEFAULT 0,
            past_saves INTEGER DEFAULT 0,
            past_conceded INTEGER DEFAULT 0,
            past_matches INTEGER DEFAULT 0,
            past_hours REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


init_db()


class GameForm(StatesGroup):
    waiting_for_stat1 = State()
    waiting_for_stat2 = State()
    waiting_for_hours = State()


class PastStatsForm(StatesGroup):
    waiting_for_past_stat1 = State()
    waiting_for_past_stat2 = State()
    waiting_for_past_matches = State()
    waiting_for_past_hours = State()


class AdminEditForm(StatesGroup):
    waiting_for_target_id = State()
    waiting_for_new_goals = State()


def get_main_keyboard(is_admin=False):
    kb = [
        [
            KeyboardButton(text="⚽ Записать матч"),
            KeyboardButton(text="📜 Добавить прошлую статистику"),
        ],
        [
            KeyboardButton(text="🪪 Карточка игрока"),
            KeyboardButton(text="👤 Выбрать позицию"),
        ],
        [
            KeyboardButton(text="🏆 Таблица лидеров"),
            KeyboardButton(text="🎯 Челлендж дня"),
        ],
        [
            KeyboardButton(text="🗑️ Удалить матч"),
            KeyboardButton(text="🌍 Статистика сообщества"),
        ],
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛡️ Админ-панель")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


async def check_ban(message: types.Message) -> bool:
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM profiles WHERE user_id = ?", (message.from_user.id,))
    res = cursor.fetchone()
    conn.close()
    if res and res[0] == 1:
        await message.answer("⛔ Вы заблокированы администратором и не можете пользоваться ботом.")
        return True
    return False


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if await check_ban(message):
        return

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

    is_admin = user_id == ADMIN_ID
    await message.answer(
        f"Привет, {message.from_user.first_name}! ⚽🔥\n\n"
        "Футбольный трекер Кокшетау активирован. Фиксируй матчи, качай свою карточку и пробивайся в топ города!",
        reply_markup=get_main_keyboard(is_admin),
    )


@dp.message(F.text == "👤 Выбрать позицию")
async def select_position(message: types.Message):
    if await check_ban(message):
        return

    btn1 = InlineKeyboardButton(text="⚽ Нападающий", callback_data="pos_Нападающий")
    btn2 = InlineKeyboardButton(text="🎯 Полузащитник", callback_data="pos_Полузащитник")
    btn3 = InlineKeyboardButton(text="🛡️ Защитник", callback_data="pos_Защитник")
    btn4 = InlineKeyboardButton(text="🧤 Вратарь", callback_data="pos_Вратарь")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn1], [btn2], [btn3], [btn4]])
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

    await callback.message.edit_text(f"Позиция успешно обновлена: {position}! ⚡")
    await callback.answer()


@dp.message(F.text == "📜 Добавить прошлую статистику")
async def start_past_stats(message: types.Message, state: FSMContext):
    if await check_ban(message):
        return

    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT position FROM profiles WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()

    pos = res[0] if res else "Не указана"
    await state.update_data(position=pos)
    await state.set_state(PastStatsForm.waiting_for_past_stat1)

    if pos == "Вратарь":
        await message.answer("📜 Сколько всего **сейвов** ты сделал до этого?")
    else:
        await message.answer("📜 Сколько всего **голов** ты забил до этого?")


@dp.message(PastStatsForm.waiting_for_past_stat1)
async def process_past_stat1(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число:")
        return
    await state.update_data(val1=int(message.text))
    data = await state.get_data()
    await state.set_state(PastStatsForm.waiting_for_past_stat2)
    if data["position"] == "Вратарь":
        await message.answer("🥅 Сколько мячей ты **пропустил** до этого?")
    else:
        await message.answer("🤝 Сколько всего **ассистов** отдал до этого?")


@dp.message(PastStatsForm.waiting_for_past_stat2)
async def process_past_stat2(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число:")
        return
    await state.update_data(val2=int(message.text))
    await state.set_state(PastStatsForm.waiting_for_past_matches)
    await message.answer("👟 Сколько примерно матчей сыграл до этого?")


@dp.message(PastStatsForm.waiting_for_past_matches)
async def process_past_matches(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число матчей:")
        return
    await state.update_data(past_matches=int(message.text))
    await state.set_state(PastStatsForm.waiting_for_past_hours)
    await message.answer("⏱️ Сколько примерно часов провел на поле суммарно?")


@dp.message(PastStatsForm.waiting_for_past_hours)
async def process_past_hours(message: types.Message, state: FSMContext):
    try:
        past_hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи корректное число часов:")
        return

    data = await state.get_data()
    v1, v2, pm = data["val1"], data["val2"], data["past_matches"]
    pos = data["position"]
    user_id = message.from_user.id
    username = (
        message.from_user.username
        or message.from_user.first_name
        or "Игрок"
    )

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    if pos == "Вратарь":
        cursor.execute(
            """
            INSERT INTO profiles (user_id, username, position, past_saves, past_conceded, past_matches, past_hours) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
            past_saves = ?, past_conceded = ?, past_matches = ?, past_hours = ?, username = ?
        """,
            (user_id, username, pos, v1, v2, pm, past_hours, v1, v2, pm, past_hours, username),
        )
    else:
        cursor.execute(
            """
            INSERT INTO profiles (user_id, username, position, past_goals, past_assists, past_matches, past_hours) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
            past_goals = ?, past_assists = ?, past_matches = ?, past_hours = ?, username = ?
        """,
            (user_id, username, pos, v1, v2, pm, past_hours, v1, v2, pm, past_hours, username),
        )

    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        "✅ Прошлые данные успешно сохранены!",
        reply_markup=get_main_keyboard(user_id == ADMIN_ID),
    )


@dp.message(F.text == "⚽ Записать матч")
async def start_add_game(message: types.Message, state: FSMContext):
    if await check_ban(message):
        return

    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT position FROM profiles WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()

    pos = res[0] if res else "Не указана"
    await state.update_data(position=pos)
    await state.set_state(GameForm.waiting_for_stat1)

    if pos == "Вратарь":
        await message.answer("🧤 Сколько **сейвов** ты сделал в этом матче?")
    else:
        await message.answer("⚽ Сколько **голов** ты забил в этом матче?")


@dp.message(GameForm.waiting_for_stat1)
async def process_stat1(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число:")
        return
    val1 = int(message.text)
    if val1 > 20:
        await message.answer("⚠️ Слишком большое число для одного матча! Введи реальное значение:")
        return
    await state.update_data(val1=val1)
    data = await state.get_data()

    await state.set_state(GameForm.waiting_for_stat2)
    if data["position"] == "Вратарь":
        await message.answer("🥅 Сколько мячей ты **пропустил** в этом матче?")
    else:
        await message.answer("🤝 Сколько **ассистов** отдал?")


@dp.message(GameForm.waiting_for_stat2)
async def process_stat2(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи целое число:")
        return
    val2 = int(message.text)
    if val2 > 20:
        await message.answer("⚠️ Слишком большое число! Введи реальное значение:")
        return
    await state.update_data(val2=val2)
    await state.set_state(GameForm.waiting_for_hours)
    await message.answer("⏱️ Сколько часов длился матч/тренировка? (например: 1.5)")


@dp.message(GameForm.waiting_for_hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи корректное число часов:")
        return

    data = await state.get_data()
    v1, v2 = data["val1"], data["val2"]
    pos = data["position"]
    today = datetime.now().strftime("%d.%m.%Y")
    user_id = message.from_user.id
    username = (
        message.from_user.username
        or message.from_user.first_name
        or "Игрок"
    )

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    if pos == "Вратарь":
        cursor.execute(
            "INSERT INTO matches (user_id, username, date, saves, conceded, hours) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, today, v1, v2, hours),
        )
    else:
        cursor.execute(
            "INSERT INTO matches (user_id, username, date, goals, assists, hours) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, today, v1, v2, hours),
        )

    cursor.execute(
        "INSERT OR IGNORE INTO profiles (user_id, username, position) VALUES (?, ?, ?)",
        (user_id, username, pos),
    )
    conn.commit()
    conn.close()

    await state.clear()
    text_msg = "✅ Матч успешно сохранен!\n⏱️ Время: " + str(hours) + " ч."
    await message.answer(text_msg, reply_markup=get_main_keyboard(user_id == ADMIN_ID))


@dp.message(F.text == "🪪 Карточка игрока")
async def show_player_card(message: types.Message):
    if await check_ban(message):
        return

    user_id = message.from_user.id
    name = message.from_user.first_name

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT position, past_goals, past_assists, past_saves, past_conceded, past_matches, past_hours FROM profiles WHERE user_id = ?",
        (user_id,),
    )
    prof = cursor.fetchone()
    cursor.execute(
        "SELECT SUM(goals), SUM(assists), SUM(saves), SUM(conceded), SUM(hours), COUNT(id) FROM matches WHERE user_id = ?",
        (user_id,),
    )
    m_data = cursor.fetchone()
    conn.close()

    pos = prof[0] if prof and prof[0] else "Не указана"
    pg, pa, ps, pc, pm, ph = (prof[1], prof[2], prof[3], prof[4], prof[5], prof[6]) if prof else (0, 0, 0, 0, 0, 0.0)
    bg, ba, bs, bc, bh, bm = (m_data[0], m_data[1], m_data[2], m_data[3], m_data[4], m_data[5]) if m_data and m_data[4] is not None else (0, 0, 0, 0, 0.0, 0)

    total_matches = (pm or 0) + (bm or 0)
    total_hours = (ph or 0.0) + (bh or 0.0)

    if pos == "Вратарь":
        total_saves = (ps or 0) + (bs or 0)
        total_conceded = (pc or 0) + (bc or 0)
        card_text = (
            f"╔═══════════════════════╗\n"
            f" 🧤 **ВРАТАРСКАЯ КАРТОЧКА** 🧤\n"
            f"╚═══════════════════════╝\n\n"
            f"👤 Игрок: **{name}**\n"
            f"🆔 ID: `{user_id}`\n"
            f"📍 Позиция: **{pos}**\n\n"
            f"📊 **СТАТИСТИКА:**\n"
            f"• Сейвы (🧤): **{total_saves}**\n"
            f"• Пропущенные (🥅): **{total_conceded}**\n\n"
            f"👟 Сыграно матчей: **{total_matches}**\n"
            f"⏱️ Наиграно времени: **{total_hours:.1f} ч.**\n"
            f"🏙️ Город: **Кокшетау**\n"
            f"─────────────────────────"
        )
    else:
        total_goals = (pg or 0) + (bg or 0)
        total_assists = (pa or 0) + (ba or 0)
        impact = total_goals + total_assists
        card_text = (
            f"╔═══════════════════════╗\n"
            f" ⚡ **ФУТБОЛЬНАЯ КАРТОЧКА** ⚡\n"
            f"╚═══════════════════════╝\n\n"
            f"👤 Игрок: **{name}**\n"
            f"🆔 ID: `{user_id}`\n"
            f"📍 Позиция: **{pos}**\n\n"
            f"📊 **СТАТИСТИКА (Г + П):**\n"
            f"• Голы (⚽): **{total_goals}**\n"
            f"• Ассисты (🤝): **{total_assists}**\n"
            f"• Общий импакт: **{impact} очков**\n\n"
            f"👟 Сыграно матчей: **{total_matches}**\n"
            f"⏱️ Наиграно времени: **{total_hours:.1f} ч.**\n"
            f"🏙️ Город: **Кокшетау**\n"
            f"─────────────────────────"
        )

    await message.answer(card_text, parse_mode="Markdown")


@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if await check_ban(message):
        return

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.user_id, p.username, p.position,
               (COALESCE(p.past_goals, 0) + COALESCE(p.past_assists, 0) + 
                COALESCE(SUM(m.goals), 0) + COALESCE(SUM(m.assists), 0)) as impact,
               (COALESCE(p.past_saves, 0) + COALESCE(SUM(m.saves), 0)) as saves
        FROM profiles p
        LEFT JOIN matches m ON p.user_id = m.user_id
        WHERE p.is_banned = 0
        GROUP BY p.user_id ORDER BY impact DESC, saves DESC LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Пока нет игроков в топе.")
        return

    text = "🏆 **ТОП-10 ИГРОКОВ КОКШЕТАУ:**\n\n"
    for i, r in enumerate(rows):
        uid, uname, position, imp, sav = r
        if position == "Вратарь":
            text += f"{i+1}. 🧤 **{uname}** (ID: `{uid}`) — **{sav}** сейвов\n"
        else:
            text += f"{i+1}. ⚽ **{uname}** (ID: `{uid}`) — **{imp}** очков Г+П\n"

    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "🌍 Статистика сообщества")
async def show_global(message: types.Message):
    if await check_ban(message):
        return

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(past_goals), SUM(past_assists), SUM(past_saves), SUM(past_matches), SUM(past_hours) FROM profiles WHERE is_banned = 0")
    pg, pa, ps, pm, ph = cursor.fetchone()
    cursor.execute("SELECT SUM(goals), SUM(assists), SUM(saves), COUNT(id), SUM(hours) FROM matches")
    bg, ba, bs, bm, bh = cursor.fetchone()
    conn.close()

    tg = (pg or 0) + (bg or 0)
    ta = (pa or 0) + (ba or 0)
    ts = (ps or 0) + (bs or 0)
    tm = (pm or 0) + (bm or 0)
    th = (ph or 0.0) + (bh or 0.0)

    await message.answer(
        f"🌍 **СТАТИСТИКА СООБЩЕСТВА КОКШЕТАУ:**\n\n"
        f"⚽ Всего голов: **{tg}**\n"
        f"🤝 Всего ассистов: **{ta}**\n"
        f"🧤 Всего сейвов: **{ts}**\n"
        f"👟 Всего матчей: **{tm}**\n"
        f"⏱️ Всего часов на поле: **{th:.1f} ч.**",
        parse_mode="Markdown",
    )


@dp.message(F.text == "🎯 Челлендж дня")
async def challenge(message: types.Message):
    if await check_ban(message):
        return

    ex = [
        "Сделай 50 передач в стену правой ногой",
        "Сделай 50 передач в стену левой ногой",
        "Сделай 20 челночных рывков по 30 метров",
        "Для вратарей: сделай 30 уверенных пойманий мяча",
    ]
    await message.answer(f"🎯 **Челлендж на сегодня:**\n\n👉 *{random.choice(ex)}*", parse_mode="Markdown")


@dp.message(F.text == "🗑️ Удалить матч")
async def del_match(message: types.Message):
    if await check_ban(message):
        return

    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, goals, assists, saves FROM matches WHERE user_id = ? ORDER BY id DESC LIMIT 5",
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
                text=f"❌ [{r[1]}] Г:{r[2]} П:{r[3]} Сейвов:{r[4]}",
                callback_data=f"del_{r[0]}",
            )
        ]
        for r in rows
    ]
    await message.answer("Выбери матч для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))


@dp.callback_query(F.data.startswith("del_"))
async def remove_match(callback: types.CallbackQuery):
    m_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM matches WHERE id = ? AND user_id = ?", (m_id, callback.from_user.id))
    conn.commit()
    conn.close()
    await callback.message.edit_text("🗑️ Матч удален!")
    await callback.answer()


@dp.message(F.text == "🛡️ Админ-панель")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У тебя нет доступа к этой панели.")
        return

    b_btn = InlineKeyboardButton(text="🔨 Забанить игрока (ЧС)", callback_data="adm_ban")
    u_btn = InlineKeyboardButton(text="🔓 Разбанить игрока", callback_data="adm_unban")
    r_b
