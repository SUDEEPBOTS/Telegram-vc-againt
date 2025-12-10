import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from pytgcalls import PyTgCalls
from pytgcalls import idle
from pytgcalls.types import MediaStream
import google.generativeai as genai
import edge_tts

# --- 1. CONFIGURATION (Loaded from Railway Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
SESSION_STRING = os.environ.get("SESSION_STRING")

# --- 2. SETUP ---
# Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Telegram & PyTgCalls
try:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    app = PyTgCalls(client)
except Exception as e:
    print(f"Login Failed! Check Session String. Error: {e}")

# Global Variable to track active chat
current_vc_chat_id = None

# --- 3. HELPER FUNCTIONS ---

async def text_to_speech(text, filename="reply_audio.mp3"):
    """Text ko Hinglish Audio mein convert karega"""
    try:
        # 'hi-IN-SwaraNeural' best hai Hinglish ke liye
        communicate = edge_tts.Communicate(text, "hi-IN-SwaraNeural")
        await communicate.save(filename)
        return filename
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# --- 4. COMMANDS & HANDLERS ---

@client.on(events.NewMessage(pattern="^/Vc on$"))
async def join_vc(event):
    """VC Join karne ka command"""
    global current_vc_chat_id
    chat_id = event.chat_id
    current_vc_chat_id = chat_id
    
    await event.reply("🔄 **Joining Voice Chat...**")
    
    try:
        await app.start() # Ensure app is running
        # Ek dummy stream play karke join karte hain taaki connection bana rahe
        await app.play(
            chat_id,
            MediaStream("http://docs.google.com/uc?export=open&id=1s5-t8Ma8c0n7-e1r8Vq4aL8W9z9v9q-1")
        )
        await event.reply("✅ **Connected!**\nAb mujhe Voice Note bhejo, main sununga aur bolunga.")
    except Exception as e:
        await event.reply(f"❌ Join Error: {e}")

@client.on(events.NewMessage(pattern="^/Vc off$"))
async def leave_vc(event):
    """VC Leave karne ka command"""
    global current_vc_chat_id
    try:
        await app.leave_call(event.chat_id)
        current_vc_chat_id = None
        await event.reply("👋 **Left Voice Chat.**")
    except Exception as e:
        await event.reply(f"❌ Leave Error: {e}")

@client.on(events.NewMessage)
async def handle_voice_msg(event):
    """Voice Note sunkar jawab dene ka logic"""
    global current_vc_chat_id
    
    # Check: Kya ye wahi chat hai jahan VC on hai? Aur kya ye Voice msg hai?
    if event.chat_id != current_vc_chat_id or not event.voice:
        return

    # User ko batao hum sun rahe hain
    status_msg = await event.reply("👂 Sun raha hoon...")

    try:
        # Step A: Audio Download
        audio_path = await event.download_media()
        
        # Step B: Gemini (Speech-to-Text + Reply Generation)
        gemini_audio = genai.upload_file(audio_path)
        
        prompt = """
        Tum ek cool Userbot ho. Is audio ko suno.
        User jo bol raha hai uska jawab 'Hinglish' (Hindi+English mix) mein do.
        Jawab bohot chota (1-2 sentence), funny aur natural hona chahiye.
        """
        
        response = model.generate_content([prompt, gemini_audio])
        reply_text = response.text
        
        # Text reply update karo (Log ke liye)
        await status_msg.edit(f"🗣 **Bolega:** {reply_text}")

        # Step C: Generate Audio (TTS)
        tts_file = await text_to_speech(reply_text)

        if tts_file:
            # Step D: Play in VC
            await app.play(
                event.chat_id,
                MediaStream(tts_file)
            )
            
            # Cleanup
            os.remove(audio_path)
            # os.remove(tts_file) # Optional: Baad mein delete karein

    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")

# --- 5. STARTUP ---
async def main():
    print("🚀 Bot Starting on Railway...")
    await client.start()
    
    # PyTgCalls client start karna zaroori hai
    # Note: Humne upar command mein app.start() handle kiya hai, 
    # par safe side ke liye yahan bhi check kar sakte hain.
    
    print("✅ Bot is Online! Use '/Vc on' in your group.")
    await idle()

if __name__ == '__main__':
    asyncio.run(main())
      
