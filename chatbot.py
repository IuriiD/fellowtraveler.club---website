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
print('########### chatbot.py - new session ############')

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
bot = telebot.TeleBot(TG_TOKEN)

contexts = []

@bot.callback_query_handler(func=lambda call: True)
def classifier(call):
    print('call.data: {}'.format(call.data))
    bot.answer_callback_query(call.id, text="")
    if (call.data == 'yes_no_menu_yes' or call.data == 'yes_no_menu_no'):
        if 'if_journey_info_needed' in contexts:
            journey_info(call.message.chat.id)
            contexts.remove('if_journey_info_needed')
        else:
            speech = dialogflow(call.data, call.message.chat.id)['speech']
            bot.send_message(call.message.chat.id, speech)
            time.sleep(2)
            bot.send_message(call.message.chat.id, 'What would you like to do next?', reply_markup=chatbot_markup.intro_menu)

@bot.message_handler(commands = ['start'])
def start_handler(message):
    if 'if_journey_info_needed' not in contexts:
        new_friend = message.from_user.first_name
        bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/ft-1.jpg', caption='Hello, {}!\nMy name is <strong>Teddy</strong>. I\'m a traveler.\nMy dream is to see the world'.format(new_friend), parse_mode='html')
        time.sleep(3)
        msg = bot.send_message(message.chat.id, 'Do you want to know more about my journey?', reply_markup=chatbot_markup.yes_no_menu)
        contexts.append('if_journey_info_needed')
        print('contexts: {}'.format(contexts))
        print('message_reply: {}'.format(msg))
        bot.register_next_step_handler(msg, if_journey_info_needed)

def if_journey_info_needed(message):
    intent = dialogflow(message, message.chat.id)['intent']
    if 'if_journey_info_needed' in contexts and intent == 'smalltalk.confirmation.no':
        pass
    elif 'if_journey_info_needed' in contexts and intent == 'smalltalk.confirmation.yes':
        journey_info(message.chat.id)
    contexts.remove('if_journey_info_needed')
    print('Communicating with DF')
    print('message in journey_info: {}'.format(message))
    print('intent: {}'.format(intent))

def journey_info(chat_id):
        time.sleep(2)
        bot.send_message(chat_id, 'Ok, here is my story')
        time.sleep(2)
        bot.send_message(chat_id, 'I came from Cherkasy city, Ukraine, from a family with 3 nice small kids')
        bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-4.jpg')
        time.sleep(4)
        bot.send_message(chat_id,
                         'So far the map of my journey looks as follows:',
                         parse_mode='html')
        bot.send_chat_action(chat_id, action='upload_photo')
        bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-3.jpg', caption='<a href="{}">Open map in browser</a>'.format('https://fellowtraveler.club/#journey_map'), parse_mode='html', reply_markup=chatbot_markup.next_or_help_menu)

def dialogflow(message, chat_id, lang_code='en'):
    query = message.text
    sessionID = message.chat.id

    URL = 'https://api.dialogflow.com/v1/query?v=20170712'
    HEADERS = {'Authorization': 'Bearer ' + DF_TOKEN, 'content-type': 'application/json'}
    payload = {'query': query, 'sessionId': sessionID, 'lang': lang_code}
    r = requests.post(URL, data=json.dumps(payload), headers=HEADERS).json()
    intent = r.get('result').get('metadata').get('intentName')
    speech = r.get('result').get('fulfillment').get('speech')
    status = r.get('status').get('code')
    output = {
        'status': status,
        'intent': intent,
        'speech': speech
    }
    return output

@bot.message_handler(commands = ['show_your_travel'])
def show_travel(message):
    bot.send_message(message.chat.id, 'Oh, I have been to many places ;)')
    bot.send_chat_action(message.chat.id, action='typing')
    bot.send_message(message.chat.id, 'Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)Oh, I have been to many places ;)')


@bot.message_handler(commands = ['add_location'])
def add_location(message):
    bot.send_message(message.chat.id, 'Ok. First please enter the secret code from the toy')
    bot.send_chat_action(message.chat.id, action='find_location')
    bot.send_venue(message.chat.id, latitude=49.4384197, longitude=32.0800805, title='Hello', address='U chorta na kulichkah')
    bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/ft-3.jpg', reply_markup=chatbot_markup.intro_menu)

@bot.message_handler(content_types = ['text'])
def text_handler(message):
    # Communicating with DF API v1 directly
    query = message.text
    sessionID = message.chat.id
    lang_code = 'en'

    URL = 'https://api.dialogflow.com/v1/query?v=20170712'
    HEADERS = {'Authorization': 'Bearer ' + DF_TOKEN, 'content-type': 'application/json'}
    payload = {'query': query, 'sessionId': sessionID, 'lang': lang_code}
    r = requests.post(URL, data=json.dumps(payload), headers=HEADERS).json()
    intent = r['result']['metadata']['intentName']
    speech = r['result']['fulfillment']['speech']
    if speech == '':
        speech = 'Hmm.. what?'
    speech += ' Intent: {}'.format(intent)
    print(r)
    bot.send_message(message.chat.id, speech)

bot.polling(True, timeout=1)

# Run Flask server
if __name__ == '__main__':
    app.run()
