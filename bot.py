import json
import os
from uuid import uuid4
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, Application
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

MEDIA_DB_FILE = "media_db.json"
if os.path.exists(MEDIA_DB_FILE):
    with open(MEDIA_DB_FILE, "r") as f:
        media_db = json.load(f)
else:
    media_db = []

def save_db():
    with open(MEDIA_DB_FILE, "w") as f:
        json.dump(media_db, f, indent=2)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send media with a caption. Use /search <keyword> to search.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    file_id = None
    media_type = None

    if msg.photo:
        file_id = msg.photo[-1].file_id
        media_type = "photo"
    elif msg.video:
        file_id = msg.video.file_id
        media_type = "video"
    elif msg.document:
        file_id = msg.document.file_id
        media_type = "document"

    if file_id and msg.caption:
        entry = {
            "id": str(uuid4()),
            "file_id": file_id,
            "media_type": media_type,
            "description": msg.caption,
            "username": msg.from_user.username or "unknown"
        }
        media_db.append(entry)
        save_db()
        await msg.reply_text("✅ Media saved!")
    else:
        await msg.reply_text("⚠️ Please send a media file with a caption.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /search <keyword>")
        return

    query = " ".join(context.args).lower()
    results = [item for item in media_db if "description" in item and query in item["description"].lower()]

    if results:
        for item in results:
            try:
                media_type = item.get("media_type")
                file_id = item.get("file_id")
                caption = item.get("description", "")
                if not media_type or not file_id:
                    continue  # skip invalid entries
                
                if media_type == "photo":
                    await update.message.reply_photo(file_id, caption=caption)
                elif media_type == "video":
                    await update.message.reply_video(file_id, caption=caption)
                elif media_type == "document":
                    await update.message.reply_document(file_id, caption=caption)
                else:
                    await update.message.reply_text(f"Unsupported media type: {media_type}")
            except Exception:
                entry_id = item.get("id", "unknown")
                await update.message.reply_text(f"(Failed to send media: {entry_id})")
    else:
        await update.message.reply_text("No matching media found.")

# --- App Setup ---
bot_app: Application = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    bot_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("search", search))
    bot_app.add_handler(MessageHandler(filters.ALL, handle_media))

    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

    print("✅ Telegram bot polling started")

    yield

    print("⏹️ Telegram bot polling stopping")
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- FastAPI Routes ---
@app.get("/")
def root():
    return {"message": "Telegram media bot API is running!"}

@app.get("/media")
def get_all_media():
    return media_db

@app.get("/search")
def search_media(q: str):
    query = q.lower()
    return [item for item in media_db if query in item["description"].lower()]
