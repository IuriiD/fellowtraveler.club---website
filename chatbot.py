# Writing Telegram bot using PyTelegramBotAPI (telebot)
# https://www.smartspate.com/how-to-create-a-telegram-bot-from-scratch-tutorial/
import telebot
import apiai, json
TG_TOKEN = '534502321:AAHOUZhwuHhpt92CiKVggGozuOADgqDBLTY'
DF_TOKEN = '301915af2ca74af7b4ed82437f90510f'
bot = telebot.TeleBot(TG_TOKEN)

@bot.message_handler(commands = ['start'])
def start_handler(message):
    bot.send_message(message.chat.id, 'Hello my little friend')
    bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/pb-3.jpg')

@bot.message_handler(commands = ['show_travel_history'])
def start_handler(message):
    bot.send_message(message.chat.id, 'Oh, I have been to many places ;)')
    bot.send_chat_action(message.chat.id, action='typing')
    bot.send_message(message.chat.id, 'Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)')
    bot.send_message(message.chat.id, '2nd message')

@bot.message_handler(commands = ['add_place'])
def start_handler(message):
    bot.send_message(message.chat.id, 'Ok. First please enter the secret code from the toy')
    bot.send_chat_action(message.chat.id, action='find_location')
    bot.send_venue(message.chat.id, latitude=49.4384197, longitude=32.0800805, title='Hello', address='U chorta na kulichkah')

@bot.message_handler(content_types = ['text'])
def text_handler(message):
    request = apiai.ApiAI(DF_TOKEN).text_request()
    request.lang = 'en-GB'
    request.session_id = message.chat.id
    request.query = message.text
    responseJson = json.loads(request.getresponse().read().decode('utf-8'))
    response = responseJson['result']['fulfillment']['speech']
    intent = responseJson['result']['action']
    if response == '':
        response = 'Hmm.. what?'
    response += ' Intent: {}'.format(intent)
    #with open('df.txt', 'w') as f:
    #    f.write(str(responseJson))
    bot.send_message(message.chat.id, response)

bot.polling()

'''
# Bot using python-telegram-bot library
# https://www.smartspate.com/how-to-create-a-telegram-bot-with-ai-in-30-lines-of-code-in-python/
# Settings
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import apiai, json
updater = Updater(token='534502321:AAHOUZhwuHhpt92CiKVggGozuOADgqDBLTY')
dispatcher = updater.dispatcher

# Commands
def startCommand(bot, update):
    bot.send_message(chat_id = update.message.chat_id, text = 'Hi! My name is Teddy! Let\'s talk?')

def textMessage(bot, update):
    # Sending message to DF and requesting answer
    request = apiai.ApiAI('301915af2ca74af7b4ed82437f90510f').text_request()
    request.lang = 'en-GB'
    request.session_id = 'FellowtravelerTeddyBot'
    request.query = update.message.text
    print('User says: {}'.format(update.message.text))
    responseJson = json.loads(request.getresponse().read().decode('utf-8'))
    response = responseJson['result']['fulfillment']['speech']

    print('Dialogflow answers: {}'.format(response))
    if response:
        bot.send_message(chat_id=update.message.chat_id, text=response)
    else:
        bot.send_message(chat_id=update.message.chat_id, text='Sorry, I didn\'t get that')

# Handlers
start_command_handler = CommandHandler('start', startCommand)
text_message_handler = MessageHandler(Filters.text, textMessage)
dispatcher.add_handler(start_command_handler)
dispatcher.add_handler(text_message_handler)
updater.start_polling(clean = True)
updater.idle()

# Using Dialogflow API v1
import requests, json
from keys import DIALOFLOW_CLIENT_ACCESS_TOKEN

URL = 'https://api.dialogflow.com/v1/query?v=20170712'
HEADERS = {'Authorization': 'Bearer ' + DIALOFLOW_CLIENT_ACCESS_TOKEN, 'content-type': 'application/json'}

query = 'How are you?'
sessionID = '1234567890'
lang_code = 'en'

payload = {'query': query, 'sessionId': sessionID, 'lang': lang_code}
r = requests.post(URL, data=json.dumps(payload), headers=HEADERS).json()
print(r.get('result').get('fulfillment').get('speech'))
'''
