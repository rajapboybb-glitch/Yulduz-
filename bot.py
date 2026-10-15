import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import yt_dlp

# --- SOZLAMALAR ---
TOKEN = os.getenv("8958554064:AAEECvtT4QmjKTnzJQd8keBSjjWqh_W4KI0")
ADMIN_ID = int(os.getenv("8738813282", "0"))
PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    raise ValueError("DIQQAT: BOT_TOKEN topilmadi!")

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

USERS = set()
CHANNELS = []

SETTINGS = {
    "audio_enabled": True,
    "sub_enabled": True
}

class AdminState(StatesGroup):
    waiting_for_channel = State()
    waiting_for_broadcast = State()

# --- WEB SERVER ---
async def handle_ping(request):
    return web.Response(text="Bot is online and running successfully!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- MAJBURIY OBUNA ---
async def check_subscription(user_id: int) -> list:
    if not SETTINGS["sub_enabled"] or user_id == ADMIN_ID:
        return []
    
    not_subscribed = []
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append(channel)
        except Exception as e:
            logging.error(f"Kanalni tekshirish xatosi {channel}: {e}")
    return not_subscribed

def get_channel_keyboard(channels):
    keyboard = []
    for ch in channels:
        url = f"https://t.me/{ch.replace('@', '')}" if not str(ch).startswith("-100") else f"https://t.me/c/{str(ch).replace('-100', '')}/1"
        keyboard.append([types.InlineKeyboardButton(text="Kanalga a'zo bo'lish", url=url)])
    keyboard.append([types.InlineKeyboardButton(text="Obunani tekshirish", callback_data="check_sub")])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    USERS.add(message.from_user.id)
    not_sub = await check_subscription(message.from_user.id)
    if not_sub:
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=get_channel_keyboard(not_sub))
        return
    await message.answer("Salom! Instagram va boshqa tarmoqlardan video havolasini yuboring.")

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery):
    not_sub = await check_subscription(callback.from_user.id)
    if not_sub:
        await callback.answer("Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await callback.message.delete()
        await callback.message.answer("Obuna tasdiqlandi! Endi havola yuborishingiz mumkin.")

# --- ADMIN PANEL ---
def get_admin_keyboard():
    audio_status = "Yoqilgan" if SETTINGS["audio_enabled"] else "O'chirilgan"
    sub_status = "Yoqilgan" if SETTINGS["sub_enabled"] else "O'chirilgan"
    
    keyboard = [
        [types.InlineKeyboardButton(text="Kanal qo'shish", callback_data="add_channel"),
         types.InlineKeyboardButton(text="Kanallar ro'yxati", callback_data="list_channels")],
        [types.InlineKeyboardButton(text=f"Audio ajratish: {audio_status}", callback_data="toggle_audio")],
        [types.InlineKeyboardButton(text=f"Majburiy obuna: {sub_status}", callback_data="toggle_sub")],
        [types.InlineKeyboardButton(text="Statistika", callback_data="admin_stats"),
         types.InlineKeyboardButton(text="Xabar tarqatish", callback_data="start_broadcast")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Admin Paneli:", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "toggle_audio")
async def toggle_audio(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    SETTINGS["audio_enabled"] = not SETTINGS["audio_enabled"]
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard())
    await callback.answer("O'zgardi!")

@dp.callback_query(F.data == "toggle_sub")
async def toggle_sub(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    SETTINGS["sub_enabled"] = not SETTINGS["sub_enabled"]
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard())
    await callback.answer("O'zgardi!")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer(f"Jami foydalanuvchilar: {len(USERS)} ta", show_alert=True)

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Kanal username yoki ID raqamini yuboring (Masalan: @mychannel):")
    await state.set_state(AdminState.waiting_for_channel)
    await callback.answer()

@dp.message(AdminState.waiting_for_channel)
async def add_channel_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    channel = message.text.strip()
    if channel not in CHANNELS:
        CHANNELS.append(channel)
        await message.answer(f"{channel} muvaffaqiyatli qo'shildi!")
    else:
        await message.answer("Bu kanal allaqachon qo'shilgan.")
    await state.clear()

@dp.callback_query(F.data == "list_channels")
async def list_channels(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    if not CHANNELS:
        await callback.answer("Kanallar ro'yxati bo'sh.", show_alert=True)
    else:
        text = "Barcha kanallar:\n" + "\n".join(CHANNELS)
        await callback.message.answer(text)
        await callback.answer()

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:")
    await state.set_state(AdminState.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast)
async def broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    count = 0
    for user_id in USERS:
        try:
            await message.copy_to(chat_id=user_id)
            count += 1
        except Exception:
            pass
    await message.answer(f"Xabar {count} ta foydalanuvchiga yuborildi.")
    await state.clear()

# --- VIDEO YUKLAB OLISH ---
@dp.message(F.text.startswith("http"))
async def handle_url(message: types.Message):
    USERS.add(message.from_user.id)
    not_sub = await check_subscription(message.from_user.id)
    if not_sub:
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=get_channel_keyboard(not_sub))
        return

    processing = await message.answer("Video yuklanmoqda...")
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'max_filesize': 50 * 1024 * 1024
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(message.text.strip(), download=True)
            filename = ydl.prepare_filename(info)

        keyboard = None
        if SETTINGS["audio_enabled"]:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="MP3 Audio yuklash", callback_data=f"audio_{os.path.basename(filename)}")]
            ])

        video_file = types.FSInputFile(filename)
        await message.answer_video(video=video_file, caption="Mana videongiz!", reply_markup=keyboard)
        await processing.delete()
        
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        await processing.edit_text("Videoni yuklashda xatolik yuz berdi.")

# --- MP3 AYLANISH ---
@dp.callback_query(F.data.startswith("audio_"))
async def convert_to_audio(callback: types.CallbackQuery):
    if not SETTINGS["audio_enabled"]:
        await callback.answer("Audio funksiyasi o'chirilgan.", show_alert=True)
        return

    filename = callback.data.replace("audio_", "")
    file_path = os.path.join("downloads", filename)
    audio_path = file_path.rsplit(".", 1)[0] + ".mp3"

    if not os.path.exists(file_path):
        await callback.answer("Fayl eskirgan.", show_alert=True)
        return

    await callback.message.answer("Audio ajratib olinmoqda...")
    os.system(f"ffmpeg -i {file_path} -q:a 0 -map a {audio_path} -y")

    if os.path.exists(audio_path):
        await callback.message.answer_audio(audio=types.FSInputFile(audio_path), caption="Audiosi")
        os.remove(audio_path)
        
    await callback.answer()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    