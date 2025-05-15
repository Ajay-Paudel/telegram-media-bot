import json
import os
from uuid import uuid4
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load or initialize media database
MEDIA_DB_FILE = "media_db.json"
if os.path.exists(MEDIA_DB_FILE):
    with open(MEDIA_DB_FILE, "r") as f:
        media_db = json.load(f)
else:
    media_db = []

# Save to file
def save_db():
    with open(MEDIA_DB_FILE, "w") as f:
        json.dump(media_db, f, indent=2)

# Telegram Bot Setup using environment variable
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
    results = [item for item in media_db if query in item["description"].lower()]

    if results:
        for item in results:
            try:
                if item["media_type"] == "photo":
                    await update.message.reply_photo(item["file_id"], caption=item["description"])
                elif item["media_type"] == "video":
                    await update.message.reply_video(item["file_id"], caption=item["description"])
                elif item["media_type"] == "document":
                    await update.message.reply_document(item["file_id"], caption=item["description"])
            except:
                await update.message.reply_text(f"(Failed to send media: {item['id']})")
    else:
        await update.message.reply_text("No matching media found.")

# Run the Telegram bot in an async loop
async def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(MessageHandler(filters.ALL, handle_media))
    await app.run_polling()

# FastAPI App (renamed to `app` for Render compatibility)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add this root route here
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

# Start both bot and API
if __name__ == "__main__":
    import uvicorn

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_telegram_bot())
    uvicorn.run(app, host="0.0.0.0", port=8000)
