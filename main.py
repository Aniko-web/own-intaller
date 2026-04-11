import os
import re
import asyncio
import logging
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
import yt_dlp

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8681391709:AAGqfqpwjJdXIvSxipHNn8pBfLZ_st_65BA"  # @BotFather dan olingan token
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== YORDAMCHI FUNKSIYALAR ====================

def is_youtube_url(text: str) -> bool:
    patterns = [
        r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+",
        r"(https?://)?(www\.)?youtu\.be/\S+"
    ]
    return any(re.search(p, text) for p in patterns)

def is_instagram_url(text: str) -> bool:
    return bool(re.search(r"(https?://)?(www\.)?instagram\.com/\S+", text))

def is_url(text: str) -> bool:
    return is_youtube_url(text) or is_instagram_url(text)

def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]

# ==================== YUKLAB OLISH ====================

async def download_audio(url: str, chat_id: int) -> dict:
    """YouTube/Instagram dan audio yuklab olish"""
    output_path = DOWNLOAD_DIR / f"{chat_id}_audio"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_path) + ".%(ext)s",

        "ffmpeg_location": "/home/aniko/ffmpeg/ffmpeg-7.0.2-amd64-static",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt" if Path("cookies.txt").exists() else None,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "audio")
        duration = info.get("duration", 0)
        thumbnail = info.get("thumbnail", None)
        
    file_path = output_path.with_suffix(".mp3")
    return {
        "path": file_path,
        "title": title,
        "duration": duration,
        "thumbnail": thumbnail
    }

async def download_video(url: str, chat_id: int) -> dict:
    """YouTube/Instagram dan video yuklab olish"""
    output_path = DOWNLOAD_DIR / f"{chat_id}_video.%(ext)s"
    ydl_opts = {
        "format": "best[filesize<50M]/best[height<=720]/best",
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt" if Path("cookies.txt").exists() else None,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")
        duration = info.get("duration", 0)
        ext = info.get("ext", "mp4")
        
    # Yuklab olingan faylni topish
    for f in DOWNLOAD_DIR.glob(f"{chat_id}_video.*"):
        file_path = f
        break
    else:
        file_path = DOWNLOAD_DIR / f"{chat_id}_video.{ext}"
        
    return {
        "path": file_path,
        "title": title,
        "duration": duration,
    }

async def search_youtube(query: str, max_results: int = 5) -> list:
    """YouTube da qidirish"""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": "ytsearch",
    }
    search_query = f"ytsearch{max_results}:{query}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(search_query, download=False)
        entries = result.get("entries", [])
    
    results = []
    for entry in entries:
        if entry:
            results.append({
                "title": entry.get("title", "Noma'lum"),
                "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                "duration": entry.get("duration", 0),
                "channel": entry.get("uploader", ""),
                "id": entry.get("id", "")
            })
    return results

def format_duration(seconds: int) -> str:
    if not seconds:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎵 *Salom! Music Downloader Bot ga xush kelibsiz!*\n\n"
        "Men nima qila olaman:\n\n"
        "📥 *Link orqali yuklab olish:*\n"
        "• YouTube yoki Instagram linkini yuboring\n"
        "• Men audio yoki video tanlashni so'rayman\n\n"
        "🔍 *Musiqa qidirish:*\n"
        "• /search [musiqa nomi] — qidirish\n"
        "• Yoki shunchaki musiqa nomini yozing\n\n"
        "📌 *Misol:*\n"
        "`https://youtu.be/dQw4w9WgXcQ`\n"
        "`/search Shahzoda yulduzlar`\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Link bo'lsa
    if is_url(text):
        await handle_url(update, context, text)
    else:
        # Qidiruv
        await handle_search_query(update, context, text)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """URL ni qayta ishlash"""
    keyboard = [
        [
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{url}"),
            InlineKeyboardButton("🎬 Video (MP4)", callback_data=f"video|{url}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    source = "YouTube" if is_youtube_url(url) else "Instagram"
    await update.message.reply_text(
        f"🔗 *{source}* linki qabul qilindi!\n\nQanday formatda yuklab olishni xohlaysiz?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Musiqa qidirish"""
    msg = await update.message.reply_text(f"🔍 *\"{query}\"* qidirilmoqda...", parse_mode="Markdown")
    
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, lambda: asyncio.run(search_youtube(query))
        )
        
        if not results:
            await msg.edit_text("❌ Hech narsa topilmadi. Boshqa so'z bilan urinib ko'ring.")
            return
        
        # Natijalarni ko'rsatish
        keyboard = []
        text = f"🎵 *\"{query}\"* bo'yicha natijalar:\n\n"
        
        for i, r in enumerate(results[:5], 1):
            duration = format_duration(r["duration"])
            text += f"{i}. *{r['title']}*\n   ⏱ {duration} | 📺 {r['channel']}\n\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"🎵 {i}. {r['title'][:35]}...",
                    callback_data=f"search_audio|{r['url']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Qidirishda xato: {e}")
        await msg.edit_text(f"❌ Xatolik yuz berdi: qidirishda muammo.")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search buyrug'i"""
    if not context.args:
        await update.message.reply_text(
            "📝 Foydalanish: `/search musiqa nomi`\n\nMisol: `/search Shahzoda yulduzlar`",
            parse_mode="Markdown"
        )
        return
    
    query = " ".join(context.args)
    await handle_search_query(update, context, query)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline keyboard tugmalari"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("❌ Bekor qilindi.")
        return
    
    if "|" not in data:
        return
    
    action, url = data.split("|", 1)
    
    if action == "audio" or action == "search_audio":
        await process_audio_download(query, url)
    elif action == "video":
        await process_video_download(query, url)

async def process_audio_download(query, url: str):
    """Audio yuklab yuborish"""
    chat_id = query.message.chat_id
    
    await query.edit_message_text("⏳ Audio yuklanmoqda... Biroz kuting.")
    
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: _sync_download_audio(url, chat_id))
        
        file_path = info["path"]
        title = info["title"]
        duration = info["duration"]
        
        if not file_path.exists():
            await query.edit_message_text("❌ Fayl yuklab olinmadi. Qayta urinib ko'ring.")
            return
        
        file_size = file_path.stat().st_size / (1024 * 1024)
        
        if file_size > 50:
            await query.edit_message_text(
                f"❌ Fayl juda katta ({file_size:.1f} MB). Telegram 50 MB gacha qabul qiladi."
            )
            file_path.unlink(missing_ok=True)
            return
        
        await query.edit_message_text(f"📤 *{title[:50]}* yuborilmoqda...", parse_mode="Markdown")
        
        with open(file_path, "rb") as f:
            await query.message.reply_audio(
                audio=f,
                title=title[:64],
                duration=int(duration) if duration else None,
                caption=f"🎵 {title[:200]}\n\n📥 @{(await query.get_bot().get_me()).username}"
            )
        
        await query.edit_message_text(f"✅ *{title[:50]}* muvaffaqiyatli yuborildi!", parse_mode="Markdown")
        file_path.unlink(missing_ok=True)
        
    except Exception as e:
        logger.error(f"Audio yuklab olishda xato: {e}")
        error_msg = str(e)
        if "Sign in" in error_msg or "cookies" in error_msg.lower():
            await query.edit_message_text(
                "❌ Bu video yuklab olish uchun kirish talab qilinadi.\n"
                "Cookies fayl qo'yish kerak bo'lishi mumkin."
            )
        else:
            await query.edit_message_text(f"❌ Xatolik: {error_msg[:200]}")

async def process_video_download(query, url: str):
    """Video yuklab yuborish"""
    chat_id = query.message.chat_id
    
    await query.edit_message_text("⏳ Video yuklanmoqda... Bu biroz vaqt olishi mumkin.")
    
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: _sync_download_video(url, chat_id))
        
        file_path = info["path"]
        title = info["title"]
        duration = info["duration"]
        
        if not file_path.exists():
            await query.edit_message_text("❌ Fayl yuklab olinmadi.")
            return
        
        file_size = file_path.stat().st_size / (1024 * 1024)
        
        if file_size > 50:
            await query.edit_message_text(
                f"❌ Video juda katta ({file_size:.1f} MB).\n"
                f"Telegram 50 MB gacha qabul qiladi.\n"
                f"🎵 Audio formatida yuklashga urinib ko'ring."
            )
            file_path.unlink(missing_ok=True)
            return
        
        await query.edit_message_text(f"📤 *{title[:50]}* yuborilmoqda...", parse_mode="Markdown")
        
        with open(file_path, "rb") as f:
            await query.message.reply_video(
                video=f,
                caption=f"🎬 {title[:200]}\n\n📥 @{(await query.get_bot().get_me()).username}",
                duration=int(duration) if duration else None,
                supports_streaming=True
            )
        
        await query.edit_message_text(f"✅ *{title[:50]}* muvaffaqiyatli yuborildi!", parse_mode="Markdown")
        file_path.unlink(missing_ok=True)
        
    except Exception as e:
        logger.error(f"Video yuklab olishda xato: {e}")
        await query.edit_message_text(f"❌ Xatolik: {str(e)[:200]}")

# Sync wrappers for thread executor
def _sync_download_audio(url: str, chat_id: int) -> dict:
    return asyncio.run(download_audio(url, chat_id))

def _sync_download_video(url: str, chat_id: int) -> dict:
    return asyncio.run(download_video(url, chat_id))

# ==================== MAIN ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()