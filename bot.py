import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
import google.generativeai as genai

# 1. Servidor web básico para manter o serviço ativo na nuvem gratuita
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

# 2. Configurações de IA e Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

SYSTEM_PROMPT = """
Você é um assistente pessoal de autorreflexão e escuta ativa fundamentado na psicologia clássica e contemporânea (Terapia Cognitivo-Comportamental, Abordagem Centrada na Pessoa de Carl Rogers e Logoterapia).

Diretrizes obrigatórias:
1. Jamais forneça diagnósticos médicos (ex: 'você tem depressão/ansiedade') e nunca prescreva remédios.
2. Acolha os relatos com tom empático, sem julgamentos morais.
3. Auxilie o usuário a identificar padrões automáticos de pensamento e mecanismos de defesa subjacentes ao que ele conta.
4. Conclua SEMPRE com 1 ou 2 perguntas reflexivas que ajudem a aprofundar o autoconhecimento.
5. Caso o usuário expresse risco à própria vida ou ideação suicida, oriente a buscar auxílio profissional urgente e informe o contato do CVV (Ligue 188 no Brasil).
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

@bot.message_handler(commands=['start'])
def welcome_user(message):
    bot.reply_to(
        message,
        "Olá! Sou seu assistente reflexivo.\n\n"
        "Você pode desabafar enviando mensagens de texto ou áudios gravados direto no microfone do Telegram. "
        "Estou aqui para ouvir e te ajudar a entender seus processos."
    )

@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    chat = get_chat(message.chat.id)
    try:
        response = chat.send_message(message.text)
        split_and_send(message.chat.id, response.text)
    except Exception as e:
        bot.reply_to(message, f"Erro ao processar mensagem: {e}")

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio(message):
    bot.send_chat_action(message.chat.id, 'record_voice')
    chat = get_chat(message.chat.id)
    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        payload = {"mime_type": "audio/ogg", "data": downloaded}
        response = chat.send_message([payload, "Analise este áudio conforme suas diretrizes de reflexão psicológica."])
        split_and_send(message.chat.id, response.text)
    except Exception as e:
        bot.reply_to(message, f"Erro ao processar áudio: {e}")

if __name__ == '__main__':
    print("Bot rodando com sucesso...")
    bot.infinity_polling()
