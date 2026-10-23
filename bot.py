import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# 1. Servidor web para manter o Render acordado
class SimpleHealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot online e funcionando!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHealthServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# 2. Configurações de API
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

SYSTEM_PROMPT = """
Você é um assistente pessoal de autorreflexão e escuta ativa fundamentado na psicologia clássica e contemporânea (Terapia Cognitivo-Comportamental, Humanismo de Carl Rogers e Logoterapia).

Diretrizes:
1. Jamais forneça diagnósticos clínicos nem prescreva medicações.
2. Acolha com tom empático e ajude a identificar padrões e crenças nucleares.
3. Seja conciso, acolhedor e direto, evitando textos excessivamente longos.
4. Conclua SEMPRE com 1 ou 2 perguntas reflexivas abertas.
5. Em casos de risco à vida, forneça o contato do CVV (Ligue 188).
"""

user_sessions = {}

def get_chat(chat_id):
    if chat_id not in user_sessions:
        model = genai.GenerativeModel(
            model_name="gemini-3.8-flash",
            system_instruction=SYSTEM_PROMPT
        )
        user_sessions[chat_id] = model.start_chat(history=[])
    return user_sessions[chat_id]

def split_and_send(chat_id, text):
    for part in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
        bot.send_message(chat_id, part)

def send_with_retry(chat, payload, max_retries=2):
    """Tenta enviar a mensagem para a IA e aguarda caso atinja o limite por minuto."""
    for attempt in range(max_retries):
        try:
            return chat.send_message(payload)
        except ResourceExhausted:
            if attempt < max_retries - 1:
                time.sleep(20)  # Aguarda 20 segundos para a cota de 1 minuto reiniciar
            else:
                raise

@bot.message_handler(commands=['start'])
def welcome_user(message):
    bot.reply_to(
        message,
        "Olá! Sou seu assistente reflexivo.\n\n"
        "Você pode me enviar mensagens de texto ou áudios gravados no celular. "
        "Estou aqui para ouvir e te ajudar a compreender seus pensamentos."
    )

@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    chat = get_chat(message.chat.id)
    try:
        response = send_with_retry(chat, message.text)
        split_and_send(message.chat.id, response.text)
    except ResourceExhausted:
        bot.reply_to(message, "Estou processando muitos pensamentos no momento! Por favor, aguarde uns 20 segundos antes de enviar outra mensagem.")
    except Exception as e:
        bot.reply_to(message, f"Ocorreu um erro temporário: {e}")

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio(message):
    bot.send_chat_action(message.chat.id, 'record_voice')
    chat = get_chat(message.chat.id)
    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        payload = [{"mime_type": "audio/ogg", "data": downloaded}, "Analise este áudio conforme suas diretrizes reflexivas."]
        response = send_with_retry(chat, payload)
        split_and_send(message.chat.id, response.text)
    except ResourceExhausted:
        bot.reply_to(message, "Muitos áudios foram enviados em sequência! Aguarde cerca de 20 a 30 segundos e envie o próximo áudio.")
    except Exception as e:
        bot.reply_to(message, f"Ocorreu um erro no processamento do áudio: {e}")

if __name__ == '__main__':
    bot.infinity_polling()
