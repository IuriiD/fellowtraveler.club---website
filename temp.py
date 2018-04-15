# Writing Telegram bot using PyTelegramBotAPI (telebot)
# https://www.smartspate.com/how-to-create-a-telegram-bot-from-scratch-tutorial/
from flask import Flask
import telebot
import requests, json
from keys import FLASK_SECRET_KEY, TG_TOKEN, DF_TOKEN
from pymongo import MongoClient
import time
import chatbot_markup

print(' ')
print('########### temp.py - new session ############')

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
bot = telebot.TeleBot(TG_TOKEN)

contexts = []

@bot.callback_query_handler(func=lambda call: True)
def classifier(call):
    print('call.data: {}'.format(call.data))
    bot.answer_callback_query(call.id, text="")
    if call.data == 'yes_no_menu_yes':
        bot.send_message(call.message.chat.id, 'yes_no_menu_yes')
    elif call.data == 'yes_no_menu_no':
        bot.send_message(call.message.chat.id, 'yes_no_menu_no')
    print(call.data)

@bot.message_handler(commands = ['start'])
def start_handler(message):
    msg = bot.send_message(message.chat.id, 'Do you want to know more about my journey?', reply_markup=chatbot_markup.yes_no_menu)
    print(msg)

    #bot.register_next_step_handler(msg, journey_info)

bot.polling(True, timeout=1)

# Run Flask server
if __name__ == '__main__':
    app.run()
