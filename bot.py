import asyncio
from datetime import datetime
import io
import logging
import random
import sqlite3

import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, KeyboardButton, ReplyKeyboardMarkup
import matplotlib.pyplot as plt
import pandas as pd

# 🔑 ТВОИ КЛЮЧИ
BOT_TOKEN = "8236796974:AAGCq-RiXnh-Ui95Hm3xay-VpDje0k8X66s"
GEMINI_KEY = "AQ.Ab8RN6J0F41zfDbSpXt5OcuLQ5PDpiQIHziu7SzMkjd2qwR0-Q"

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


class CoachForm(StatesGroup):
    waiting_for_question = State()


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚽ Записать матч"),
                KeyboardButton(text="🗑️ Удалить последний"),
            ],
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="📜 История"),
            ],
            [
                KeyboardButton(text="📈 График"),
                KeyboardButton(text="🎯 Челлендж дня"),
            ],
            [KeyboardButton(text="🧠 ИИ-Тренер")],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Салам, {message.from_user.first_name}! ⚽🔥\n"
        "Твой ультимативный футбольный бот запущен и готов разрывать!",
        reply_markup=get_main_keyboard(),
    )


# --- ЗАПИСЬ МАТЧА ---
@dp.message(F.text == "⚽ Записать матч")
async def start_add_game(message: types.Message, state: FSMContext):
    await state.set_state(GameForm.waiting_for_goals)
    await message.answer("Сколько голов забил за этот матч? (Напиши цифру):")


@dp.message(GameForm.waiting_for_goals)
async def process_goals(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введи просто число (например: 0, 2, 5):")
        return

    await state.update_data(goals=int(message.text))
    await state.set_state(GameForm.waiting_for_hours)
    await message.answer("Сколько часов играл? (например: 1, 1.5, 2):")


@dp.message(GameForm.waiting_for_hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("⚠️ Введи число часов (например: 1.5 или 2):")
        return

    user_data = await state.get_data()
    goals = user_data["goals"]
    today = datetime.now().strftime("%d.%m.%Y")
    user_id = message.from_user.id

    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO matches (user_id, date, goals, hours) VALUES (?, ?, ?, ?)",
        (user_id, today, goals, hours),
    )
    conn.commit()

    cursor.execute(
        "SELECT MAX(goals) FROM matches WHERE user_id = ?", (user_id,)
    )
    max_goals = cursor.fetchone()[0]
    conn.close()

    achievement = ""
    if goals == max_goals and goals > 0:
        achievement = "\n\n🏆 **Новый личный рекорд по голам за матч!** 🔥"

    await state.clear()
    await message.answer(
        f"✅ **Матч успешно сохранен в базу!**\n📅 {today}\n⚽ Голы: {goals}\n⏱️ Время: {hours} ч.{achievement}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(),
    )


# --- УДАЛЕНИЕ ПОСЛЕДНЕГО МАТЧА ---
@dp.message(F.text == "🗑️ Удалить последний")
async def delete_last_game(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("football_bot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, date, goals, hours FROM matches WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    last_match = cursor.fetchone()

    if not last_match:
        conn.close()
        await message.answer("❌ У тебя пока нет записанных матчей.")
        return

    match_id, date, goals, hours = last_match
    cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑️ **Удален последний матч:**\n📅 {date} — ⚽ {goals} голов | ⏱️ {hours} ч.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(),
    )


# --- СТАТИСТИКА ---
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
        await message.answer("❌ Статистика пуста! Сыграй хотя бы один матч.")
        return

    total_games = len(rows)
    total_goals = sum(row[0] for row in rows)
    total_hours = sum(row[1] for row in rows)
    avg_goals = total_goals / total_games
    max_goals = max(row[0] for row in rows)

    text = (
        "--- 📊 **ТВОЯ ПРОДВИНУТАЯ СТАТИСТИКА** ---\n\n"
        f"🏃‍♂️ Всего игр: **{total_games}**\n"
        f"⚽ Всего голов: **{total_goals}**\n"
        f"⏱️ Наиграно часов: **{total_hours:.1f} ч.**\n"
        f"📈 В среднем: **{avg_goals:.1f}** гола за игру\n"
        f"👑 Рекорд голов за матч: **{max_goals}**\n"
        "------------------------------------"
    )
    await message.answer(text, parse_mode="Markdown")


# --- ИСТОРИЯ ---
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
        await message.answer("❌ История пока пуста.")
        return

    history_text = "--- 📜 **ПОСЛЕДНИЕ МАТЧИ** ---\n\n"
    for i, row in enumerate(rows, 1):
        history_text += f"{i}. 📅 {row[0]} — ⚽ {row[1]} голов | ⏱️ {row[2]} ч.\n"

    await message.answer(history_text, parse_mode="Markdown")


# --- ГРАФИК ПРОГРЕССА ---
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
            "❌ Недостаточно данных для построения графика. Запиши хотя бы пару матчей!"
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
    plt.title("Твой прогресс по голам", fontsize=14, fontweight="bold")
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
        photo=photo,
        caption="📈 **Твой текущий график результативности!**",
        parse_mode="Markdown",
    )


# --- ЕЖЕДНЕВНЫЙ ЧЕЛЛЕНДЖ ---
@dp.message(F.text == "🎯 Челлендж дня")
async def daily_challenge(message: types.Message):
    challenges = [
        "🎯 **Челлендж на сегодня:** Сделай 100 точных передач в стенку правой и левой ногой без потери контроля.",
        "⚡ **Челлендж на сегодня:** Выполни 5 челночных рывков по 30 метров на максимальной скорости с отдыхом по 45 секунд.",
        "⚽ **Челлендж на сегодня:** Потрать 15 минут исключительно на удары слёта из-за штрафной.",
        "🧠 **Челлендж на сегодня:** Отработай разворот Кройфа (Cruyff turn) или финт шведкой минимум 30 раз.",
    ]
    await message.answer(random.choice(challenges), parse_mode="Markdown")


# --- ИИ-ТРЕНЕР (ЧЕРЕЗ ПРЯМОЙ API ЗАПРОС) ---
@dp.message(F.text == "🧠 ИИ-Тренер")
async def ask_coach_start(message: types.Message, state: FSMContext):
    await state.set_state(CoachForm.waiting_for_question)
    await message.answer(
        "🧠 **ИИ-Тренер на связи!**\n\nСпроси у меня всё что угодно: про тактику, дриблинг, удары или физику:",
        parse_mode="Markdown",
    )


@dp.message(CoachForm.waiting_for_question)
async def process_coach_question(message: types.Message, state: FSMContext):
    question = message.text
    await state.clear()

    status_msg = await message.answer(
        "⏳ *Тренер анализирует твой вопрос...*", parse_mode="Markdown"
    )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {
        "Authorization": f"Bearer {GEMINI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Ты опытный футбольный тренер. Отвечай емко, давай"
                            " конкретные практические советы по технике,"
                            f" движению, дриблингу. Вопрос игрока: {question}"
                        )
                    }
                ]
            }
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ai_text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "Пустой ответ")
                    )
                else:
                    err_text = await resp.text()
                    ai_text = f"Ошибка API ({resp.status}): {err_text}"

        await status_msg.delete()
        await message.answer(
            f"💡 **Ответ ИИ-Тренера:**\n\n{ai_text}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(),
        )

    except Exception as e:
        await status_msg.delete()
        await message.answer(
            f"⚠️ Ошибка связи с ИИ: {e}", reply_markup=get_main_keyboard()
        )


async def main():
    print("🚀 Ультимативный футбольный бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
