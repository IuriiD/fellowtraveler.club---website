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
# Handling clicks on different InlineKeyboardButtons
def classifier(call):
    print('call.data: {}'.format(call.data))
    bot.answer_callback_query(call.id, text="")

    # Buttons 'Yes'/'No, thanks' in the intro block asking if user want's to know more about T. journey
    if 'if_journey_info_needed' in contexts:
        if call.data == 'Yes':
            journey_info(call.message.chat.id)
            contexts.remove('if_journey_info_needed')
        elif call.data == 'No':
            time.sleep(3)
            bot.send_message(call.message.chat.id, 'Ok. Than we can just talk ;)\nJust in case here\'s my menu',
                             reply_markup=chatbot_markup.intro_menu)
            contexts.remove('if_journey_info_needed')

    # Button 'Next' in cycle showing places visited by Teddy
    elif 'journey_next_info' in contexts:
        if call.data == 'Next':
            pass
            # I started my journey in ... on ... // block - always as there will always be the 1st location
                # Optional photo

            # Since that time I have "checked" in .. places located in [country_of_origin | N countries (country1, country2, .., countryN) // optional as there might be only 1 (starting) location
                # For eg.:
                # Since that time I have "checked" in 1 more place in Ukraine. Here it is:
                # Since that time I have "checked" in 2 more places in Ukraine. Here they are:
                # Since that time I have "checked" in 5 more places in 2 countries (Ukraine, Poland). Here they are:
                # Since that time I have "checked" in 12 more places in 6 countries (Ukraine, Poland, Italy, Bulgaria, Spain, UK). Here they are:
                    # For each location: date, map, [photo/-s], [author], [comment]
            #


    # Without context - feed input to Dialogflow, return result and menu
    else:
        speech = dialogflow(call.data, call.message.chat.id)['speech']
        print('speech: {}'.format(speech))
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
    intent = dialogflow(message.text, message.chat.id)['intent']
    speech = dialogflow(message.text, message.chat.id)['speech']
    if 'if_journey_info_needed' in contexts:
        if intent == 'smalltalk.confirmation.no':
            time.sleep(3)
            bot.send_message(message.chat.id, 'Ok. Than we can just talk ;)\nJust in case here\'s my menu',
                             reply_markup=chatbot_markup.intro_menu)
            contexts.remove('if_journey_info_needed')
        elif intent == 'smalltalk.confirmation.yes':
            journey_info(message.chat.id)
            contexts.remove('if_journey_info_needed')
        else:
            bot.send_message(message.chat.id, speech)
            time.sleep(2)
            bot.send_message(message.chat.id, 'What would you like to do next?',
                             reply_markup=chatbot_markup.intro_menu)
    else:
        bot.send_message(message.chat.id, speech)
        time.sleep(2)
        bot.send_message(message.chat.id, 'What would you like to do next?',
                         reply_markup=chatbot_markup.intro_menu)

def journey_info(chat_id):
        time.sleep(3)
        bot.send_message(chat_id, 'Ok, here is my story')
        time.sleep(5)
        bot.send_message(chat_id, 'I came from <a href="{}">Cherkasy</a> city, Ukraine, from a family with 3 nice small kids'.format('https://www.google.com/maps/place/Черкассы,+Черкасская+область,+18000/@50.5012899,25.9683426,6z'), parse_mode='html', disable_web_page_preview=True)
        bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-4.jpg')
        time.sleep(6)
        bot.send_message(chat_id,
                         'So far the map of my journey looks as follows:',
                         parse_mode='html')
        bot.send_chat_action(chat_id, action='upload_photo')
        bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-3.jpg', caption='<a href="{}">Open map in browser</a>'.format('https://fellowtraveler.club/#journey_map'), parse_mode='html', reply_markup=chatbot_markup.next_or_help_menu)
        contexts.append('journey_next_info')

def dialogflow(query, chat_id, lang_code='en'):
    URL = 'https://api.dialogflow.com/v1/query?v=20170712'
    HEADERS = {'Authorization': 'Bearer ' + DF_TOKEN, 'content-type': 'application/json'}
    payload = {'query': query, 'sessionId': chat_id, 'lang': lang_code}
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
    journey_info(message.chat.id)

@bot.message_handler(commands = ['add_location'])
def add_location(message):
    bot.send_message(message.chat.id, 'Ok. First please enter the secret code from the toy')
    bot.send_chat_action(message.chat.id, action='find_location')
    bot.send_venue(message.chat.id, latitude=49.4384197, longitude=32.0800805, title='Hello', address='U chorta na kulichkah')
    bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/ft-3.jpg', reply_markup=chatbot_markup.intro_menu)

@bot.message_handler(content_types = ['text'])
def text_handler(message):
    speech = dialogflow(message.text, message.chat.id)['speech']
    bot.send_message(message.chat.id, speech)

bot.polling(True, timeout=1)

# Run Flask server
if __name__ == '__main__':
    app.run()
