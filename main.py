import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import json
from datetime import datetime
import re

# API Anahtarları
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Görevleri sakla
tasks = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Merhaba! Ben görev takip botunuzum.\n\n"
        "📝 Bir görev tanımlamak için direkt yazın.\n"
        "Örnek: 'Dolar 35 TL altına düşünce haber ver'\n\n"
        "📋 Görevleri görmek için: /gorevler\n"
        "❌ Görev silmek için: /sil 1"
    )

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tasks:
        await update.message.reply_text("📋 Henüz görev yok.")
        return
    msg = "📋 Görevleriniz:\n\n"
    for i, task in enumerate(tasks, 1):
        msg += f"{i}. {task['description']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0]) - 1
        removed = tasks.pop(idx)
        await update.message.reply_text(f"✅ Görev silindi: {removed['description']}")
    except:
        await update.message.reply_text("❌ Kullanım: /sil 1")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    chat_id = update.message.chat_id

    prompt = f"""Kullanıcı şu görevi tanımladı: "{user_msg}"
    
Bu görevi JSON formatında döndür:
{{
  "description": "görevin kısa açıklaması",
  "type": "fiyat_takibi veya hava_durumu veya haber veya zamanlama",
  "check_interval_minutes": kontrol sıklığı dakika olarak,
  "condition": "koşulun açıklaması"
}}

Sadece JSON döndür, başka bir şey yazma."""

    response = model.generate_content(prompt)
    
    try:
        clean = response.text.replace("json", "").replace("", "").strip()
        task_data = json.loads(clean)
        task_data["chat_id"] = chat_id
        task_data["created_at"] = datetime.now().isoformat()
        tasks.append(task_data)
        
        await update.message.reply_text(
            f"✅ Görev kaydedildi!\n\n"
            f"📌 {task_data['description']}\n"
            f"⏱ Her {task_data['check_interval_minutes']} dakikada kontrol edilecek.",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text("❌ Görev anlaşılamadı, tekrar dener misiniz?")

async def check_tasks(app):
    while True:
        for task in tasks:
            try:
                prompt = f"""Şu görevi kontrol et: {json.dumps(task, ensure_ascii=False)}
                
Güncel bilgilere göre koşul gerçekleşti mi?
Eğer evet ise JSON döndür: {{"triggered": true, "message": "bildirim mesajı"}}
Eğer hayır ise: {{"triggered": false}}

Sadece JSON döndür."""

                response = model.generate_content(prompt)
                clean = response.text.replace("json", "").replace("", "").strip()
                result = json.loads(clean)
                
                if result.get("triggered"):
                    await app.bot.send_message(
                        chat_id=task["chat_id"],
                        text=f"🔔 Bildirim!\n\n{result['message']}",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                print(f"Görev kontrol hatası: {e}")
        
        await asyncio.sleep(60)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gorevler", list_tasks))
    app.add_handler(CommandHandler("sil", delete_task))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    asyncio.create_task(check_tasks(app))
    
    await app.run_polling()

if _name_ == "_main_":
    asyncio.run(main())
