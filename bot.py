#```python
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from converter import process_sticker_pack

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Replace this with your actual Bot Token from @BotFather
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a greeting when the command /start is issued."""
    welcome_message = (
        "👋 Welcome to the Tg2Wa Sticker Bridge Bot!\n\n"
        "Send me any sticker from a Telegram sticker pack, and I will "
        "convert the entire pack into a WhatsApp-compatible `.wastickers` file.\n\n"
        "Note: TGS (Animated Lottie) stickers are complex and currently skipped. "
        "Static and Video (.webm) stickers work perfectly!"
    )
    await update.message.reply_text(welcome_message)

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming stickers and processes their parent pack."""
    sticker = update.message.sticker
    
    if not sticker.set_name:
        await update.message.reply_text("This sticker doesn't belong to a sticker pack.")
        return

    pack_name = sticker.set_name
    status_msg = await update.message.reply_text(f"🔍 Found pack: `{pack_name}`\nFetching stickers...")

    try:
        # Fetch the entire sticker set from Telegram
        sticker_set = await context.bot.get_sticker_set(pack_name)
        stickers = sticker_set.stickers
        
        # WhatsApp restricts packs to 30 stickers maximum.
        # We need to split Telegram packs (which can have up to 120) into chunks.
        chunks = [stickers[i:i + 30] for i in range(0, len(stickers), 30)]
        
        await status_msg.edit_text(f"📦 Pack contains {len(stickers)} stickers. Splitting into {len(chunks)} WhatsApp pack(s)...\n\nStarting conversion. This may take a minute.")

        for i, chunk in enumerate(chunks):
            chunk_status = await update.message.reply_text(f"⏳ Processing Pack Part {i + 1}/{len(chunks)}...")
            
            # Call our converter to generate the .wastickers file
            wastickers_file, skipped = await process_sticker_pack(
                chunk, 
                sticker_set.title, 
                i + 1, 
                len(chunks), 
                context.bot
            )
            
            if wastickers_file:
                caption = f"✅ **{sticker_set.title} (Part {i + 1})**"
                if skipped > 0:
                    caption += f"\n⚠️ Skipped {skipped} animated (.tgs) stickers."
                
                caption += "\n\n📲 *How to add to WhatsApp:*\n1. Download this file.\n2. Open it with the 'Sticker Maker' app."

                with open(wastickers_file, 'rb') as doc:
                    await context.bot.send_document(
                        chat_id=update.message.chat_id,
                        document=doc,
                        filename=os.path.basename(wastickers_file),
                        caption=caption,
                        parse_mode="Markdown"
                    )
                
                # Cleanup temporary wastickers file after sending
                os.remove(wastickers_file)
                await chunk_status.delete()
            else:
                await chunk_status.edit_text("❌ Failed to create pack (maybe it only contained unsupported .tgs formats).")
        
        await status_msg.edit_text("🎉 All done! Enjoy your WhatsApp stickers.")

    except Exception as e:
        logger.error(f"Error handling sticker pack: {e}")
        await update.message.reply_text("❌ An error occurred while processing the sticker pack.")

def main():
    """Starts the bot."""
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("ERROR: Please update the BOT_TOKEN in bot.py before running.")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Stickers.ALL, handle_sticker))

    # Run the bot
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

         
