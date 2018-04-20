# -*- coding: utf-8 -*-

# from flask import Flask
import telebot
import requests, json
from keys import FLASK_SECRET_KEY, TG_TOKEN, DF_TOKEN
from pymongo import MongoClient
import time
import chatbot_markup
import tg_functions  # functions used for 'classical' website on flask (tg for TeddyGo [initial project's name]
from passlib.hash import sha256_crypt

print(' ')
print('########### chatbot.py - new session ############')

# app = Flask(__name__)
# app.secret_key = FLASK_SECRET_KEY
bot = telebot.TeleBot(TG_TOKEN)

OURTRAVELLER = 'Teddy'
SHORT_TIMEOUT = 0  # 2 # seconds, between messages for imitation of 'live' typing
MEDIUM_TIMEOUT = 0  # 4
LONG_TIMEOUT = 0  # 6

'''
    All commands can be entered either using InlineKeyboardButtons or by typing exact or close by meaning words.
    Correspondingly 2 main hadlers are used - one for InlineKeyboardButtons (@bot.callback_query_handler) and another
    for plain text input (@bot.message_handler(content_types = ['text'])). All text input is "fed" to Dialogflow to
    get intent and text responses. Conversation chains are controlled using a variable contexts (a list).

    P.s. Commands enteres via BotFather:
    start - Let's get acquainted
    help - Get help
    tell_your_story - Display this traveler's story
    you_got_fellowtraveler - Do you have it? Get info what to do next    
'''
contexts = []  # holds last state


######################################## / Handlers START ######################################

@bot.message_handler(commands=['start'])
# Block 0
def start_handler(message):
    if 'if_journey_info_needed' not in contexts:
        bot.send_message(message.chat.id, 'Hello, {}!'.format(message.from_user.first_name))
        time.sleep(SHORT_TIMEOUT)
        travelers_story_intro(message.chat.id)
        contexts.append('if_journey_info_needed')


@bot.message_handler(commands=['tell_your_story'])
def tell_your_story(message):
    travelers_story_intro(message.chat.id)
    contexts.append('if_journey_info_needed')


@bot.message_handler(commands=['help'])
def help(message):
    get_help(message)


@bot.message_handler(commands=['you_got_fellowtraveler'])
def add_location(message):
    bot.send_message(message.chat.id, 'Oh, you are special ;)\nTo proceed please enter the <i>secret code</i> from the toy', parse_mode='html')
    bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/ft-3.jpg', reply_markup=chatbot_markup.cancel_help_menu)


######################################## / Handlers END ######################################

################################### 'Custom' handlers START ##################################


@bot.message_handler(content_types=['text'])
# Handling all text input (NLP using Dialogflow and then depending on recognised intent and contexts variable
def text_handler(message):
    speech = dialogflow(message.text, message.chat.id)['speech']
    intent = dialogflow(message.text, message.chat.id)['intent']

    # Block 1. Reply to typing 'Yes'/'No' after the intro block asking if user want's to know more about T. journey
    # On exit of block if user enters 'Yes' - context 'journey_next_info', if 'No' or buttons of previous blocks -
    # contexts[] is cleared
    if 'if_journey_info_needed' in contexts:
        if intent == 'smalltalk.confirmation.no':
            time.sleep(SHORT_TIMEOUT)
            contexts.clear()
            bot.send_message(message.chat.id, 'Ok. Than we can just talk ;)\nJust in case here\'s my menu',
                             reply_markup=chatbot_markup.intro_menu)
        elif intent == 'smalltalk.confirmation.yes':
            journey_intro(message.chat.id)
            if 'if_journey_info_needed' in contexts:
                contexts.remove('if_journey_info_needed')
            contexts.append('journey_next_info')
        # If user is clicking buttons under previous blocks (for eg., buttons 'FAQ', <Traveler>'s story, You got traveler)
        # call classifier() with cleaned contexts
        else:
            contexts.clear()
            bot.send_message(message.chat.id, speech)
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(message.chat.id, 'What would you like to do next?',
                             reply_markup=chatbot_markup.intro_menu)

    # Block 2. Reply to entering 'Next/Help' after block_1 showing overall map of traveler's journey;
    # on entry - context 'journey_next_info',
    # on exit of block if user clicks
    # 1) button 'Next' and
    # a) if only 1 place visited - contexts[] is cleared
    # b) if several places were visited - 2 contexts: 'journey_summary_presented' and {'location_shown': None, 'total_locations': total_locations}
    # 2) button 'Help' or buttons of previous blocks - contexts[] is cleared
    elif 'journey_next_info' in contexts:
        if intent == 'next_info':
            total_locations = journey_begins(message.chat.id, OURTRAVELLER)
            time.sleep(SHORT_TIMEOUT)
            # If there's only 1 location, show it and present basic menu ("Teddy's story/Help/You got Teddy?")
            if total_locations == 1:
                the_1st_place(message.chat.id, OURTRAVELLER, False)
                bot.send_message(message.chat.id,
                                 'And that\'s all my journey so far ;)\n\nWhat would you like to do next? We can just talk or use this menu:',
                                 reply_markup=chatbot_markup.intro_menu)
                contexts.clear()
            # If there are >1 visited places, ask user if he wants to see them ("Yes/No/Help")
            else:
                bot.send_message(message.chat.id, 'Would you like to see all places that I have been to?',
                                 reply_markup=chatbot_markup.yes_no_help_menu)
                if 'journey_next_info' in contexts:
                    contexts.remove('journey_next_info')
                contexts.append('journey_summary_presented')
                contexts.append({'location_shown': None, 'total_locations': total_locations})
        elif intent == 'show_faq':
            contexts.clear()
            get_help(message)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            contexts.clear()
            bot.send_message(message.chat.id, speech)
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(message.chat.id, 'What would you like to do next?',
                             reply_markup=chatbot_markup.intro_menu)

    # Block 3. Reply to entering 'Yes/No,thanks/Help' after journey summary block
    # on entry - 2 contexts 'journey_summary_presented' and {'location_shown': None, 'total_locations': total_locations},
    # on exit:
    # 1) if user clicks 'Yes' - 2 contexts 'locations_iteration' and {'location_shown': 0, 'total_locations': total_locations}
    # 2) if user clicks 'No/Help' or buttons of previous blocks - contexts[] is cleared
    elif 'journey_summary_presented' in contexts:
        if intent == 'smalltalk.confirmation.yes':  # "Yes" button is available if >1 places were visited
            the_1st_place(message.chat.id, OURTRAVELLER, True)
            if 'journey_summary_presented' in contexts:
                contexts.remove('journey_summary_presented')
            contexts.append('locations_iteration')
            for context in contexts:
                if 'location_shown' in context:
                    context['location_shown'] = 0
        elif intent == 'smalltalk.confirmation.no':
            time.sleep(SHORT_TIMEOUT)
            contexts.clear()
            bot.send_message(message.chat.id, 'Ok. Than we can just talk ;)\nJust in case here\'s my menu',
                             reply_markup=chatbot_markup.intro_menu)
        elif intent == 'show_faq':
            contexts.clear()
            get_help(message)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            contexts.clear()
            bot.send_message(message.chat.id, speech)
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(message.chat.id, 'What would you like to do next?',
                             reply_markup=chatbot_markup.intro_menu)

    # Block 4. Reply to entering 'Next/Help' after block_3 showing the 1st place among several visited; is executed in cycle
    # on entry - 2 contexts: 'locations_iteration' and {'location_shown': X, 'total_locations': Y}
    # (where X = the serial number of place visited, for eg. 0 - the 1st place, 2 - the 3rd place),
    # on exit:
    # 1) if user clicks 'Yes' and
    # a) if the last place visited is shown - contexts[] is cleared
    # b) if places to show remain - 2 contexts: 'locations_iteration' and {'location_shown': X+1, 'total_locations': Y}
    # 2) button 'Help' or buttons of previous blocks - contexts[] is cleared
    elif 'locations_iteration' in contexts:
        if intent == 'next_info':
            location_shown = 0
            total_locations = 1
            for context in contexts:
                if 'location_shown' in context:
                    location_shown = context['location_shown']
                    total_locations = context['total_locations']
            if total_locations - (location_shown + 1) == 1:
                contexts.clear()
                every_place(message.chat.id, OURTRAVELLER, location_shown + 1, False)
                bot.send_message(message.chat.id,
                                 'And that\'s all my journey so far ;)\n\nWhat would you like to do next? We can just talk or use this menu:',
                                 reply_markup=chatbot_markup.intro_menu)
            elif total_locations - (location_shown + 1) > 1:
                every_place(message.chat.id, OURTRAVELLER, location_shown + 1, True)
                for context in contexts:
                    if 'location_shown' in context:
                        context['location_shown'] += 1
        elif intent == 'show_faq':
            contexts.clear()
            get_help(message)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            contexts.clear()
            bot.send_message(message.chat.id, speech)
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(message.chat.id, 'What would you like to do next?',
                             reply_markup=chatbot_markup.intro_menu)

    # Block 5. User clicked button 'You got Teddy?' and was prompted to enter the secret code
    elif 'enters_code' in contexts:
        # If user enters 'Cancel' or smth similar after entering invalid secret_code - update contexts
        if intent == 'smalltalk.confirmation.cancel':
            contexts.clear()
            bot.send_message(message.chat.id, 'Ok. What would you like to do next?',
                         reply_markup=chatbot_markup.intro_menu)
        # If user enters whatever else, not == intent 'smalltalk.confirmation.cancel'
        else:
            secret_code_entered = message.text
            if secret_code_validation(secret_code_entered, message.chat.id):
                contexts.clear()
                contexts.append('code_correct')
                bot.send_message(message.chat.id, 'Code correct, thanks! Sorry for formalities')
                bot.send_message(message.chat.id, 'What to do next:', reply_markup=chatbot_markup.you_got_teddy_menu)
            else:
                bot.send_message(message.chat.id, 'Incorrect secret code. Please try again',
                                 reply_markup=chatbot_markup.cancel_help_menu)

    # General endpoint - if user entered some text an no context exists
    else:
        # User typed 'Help' or similar
        if intent == 'show_faq':
            get_help(message)

        # User typed 'Teddy's story' or similar
        elif intent == 'tell_your_story':
            bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/ft-1.jpg',
                           caption='My name is <strong>{}</strong>. I\'m a traveler.\nMy dream is to see the world'.format(
                               OURTRAVELLER), parse_mode='html')
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(message.chat.id, 'Do you want to know more about my journey?',
                             reply_markup=chatbot_markup.yes_no_gotteddy_menu)
            contexts.append('if_journey_info_needed')

        # User typed "You got Teddy" or similar
        elif intent == 'you_got_fellowtraveler':
            bot.send_message(message.chat.id,
                             'Oh, that\'s a tiny adventure and some responsibility;)\nTo proceed please enter the <i>secret code</i> from the toy',
                             parse_mode='html')
            # Image with an example of secret code
            bot.send_photo(message.chat.id, 'https://iuriid.github.io/img/ft-3.jpg', reply_markup=chatbot_markup.cancel_help_menu)
            contexts.clear()
            contexts.append('enters_code')

        # All other text inputs
        else:
            print('speech: {}'.format(speech))
            bot.send_message(message.chat.id, speech)
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(message.chat.id, 'What would you like to do next?', reply_markup=chatbot_markup.intro_menu)


@bot.callback_query_handler(func=lambda call: True)
# Handling clicks on different InlineKeyboardButtons
def classifier(call):
    print('call.data: {}'.format(call.data))
    bot.answer_callback_query(call.id, text="")

    # Block 1. Reply to clicking on buttons 'Yes'/'No' displayed after the intro block
    # asking if user want's to know more about T. journey
    # On exit of block if user clicks 'Yes' - context 'journey_next_info', if 'No' or buttons of previous blocks -
    # contexts[] is cleared
    if 'if_journey_info_needed' in contexts:
        if call.data == 'No':
            time.sleep(SHORT_TIMEOUT)
            contexts.clear()
            bot.send_message(call.message.chat.id, 'Ok. Than we can just talk ;)\nJust in case here\'s my menu',
                             reply_markup=chatbot_markup.intro_menu)
        elif call.data == 'Yes':
            journey_intro(call.message.chat.id)
            if 'if_journey_info_needed' in contexts:
                contexts.remove('if_journey_info_needed')
            contexts.append('journey_next_info')
        # If user is clicking buttons under previous blocks (for eg., buttons 'FAQ', <Traveler>'s story, You got traveler)
        # call classifier() with cleaned contexts
        else:
            contexts.clear()
            classifier(call)

    # Block 2. Reply to buttons 'Next/Help' after block_1 showing overall map of traveler's journey;
    # on entry - context 'journey_next_info',
    # on exit of block if user clicks
    # 1) button 'Next' and
    # a) if only 1 place visited - contexts[] is cleared
    # b) if several places were visited - 2 contexts: 'journey_summary_presented' and {'location_shown': None, 'total_locations': total_locations}
    # 2) button 'Help' or buttons of previous blocks - contexts[] is cleared
    elif 'journey_next_info' in contexts:
        if call.data == 'Next':
            total_locations = journey_begins(call.message.chat.id, OURTRAVELLER)
            time.sleep(SHORT_TIMEOUT)
            # If there's only 1 location, show it and present basic menu ("Teddy's story/Help/You got Teddy?")
            if total_locations == 1:
                the_1st_place(call.message.chat.id, OURTRAVELLER, False)
                bot.send_message(call.message.chat.id,
                                 'And that\'s all my journey so far ;)\n\nWhat would you like to do next? We can just talk or use this menu:',
                                 reply_markup=chatbot_markup.intro_menu)
                contexts.clear()
            # If there are >1 visited places, ask user if he wants to see them ("Yes/No/Help")
            else:
                bot.send_message(call.message.chat.id, 'Would you like to see all places that I have been to?',
                                 reply_markup=chatbot_markup.yes_no_help_menu)
                if 'journey_next_info' in contexts:
                    contexts.remove('journey_next_info')
                contexts.append('journey_summary_presented')
                contexts.append({'location_shown': None, 'total_locations': total_locations})
        elif call.data == 'FAQ':
            contexts.clear()
            get_help(call.message)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            contexts.clear()
            classifier(call)

    # Block 3. Reply to buttons 'Yes/No,thanks/Help' displayed after journey summary block
    # on entry - 2 contexts 'journey_summary_presented' and {'location_shown': None, 'total_locations': total_locations},
    # on exit:
    # 1) if user clicks 'Yes' - 2 contexts 'locations_iteration' and {'location_shown': 0, 'total_locations': total_locations}
    # 2) if user clicks 'No/Help' or buttons of previous blocks - contexts[] is cleared
    elif 'journey_summary_presented' in contexts:
        if call.data == 'Yes': # "Yes" button is available if >1 places were visited
            the_1st_place(call.message.chat.id, OURTRAVELLER, True)
            if 'journey_summary_presented' in contexts:
                contexts.remove('journey_summary_presented')
            contexts.append('locations_iteration')
            for context in contexts:
                if 'location_shown' in context:
                    context['location_shown'] = 0
        elif call.data == 'No':
            time.sleep(SHORT_TIMEOUT)
            contexts.clear()
            bot.send_message(call.message.chat.id, 'Ok. Than we can just talk ;)\nJust in case here\'s my menu',
                             reply_markup=chatbot_markup.intro_menu)
        elif call.data == 'FAQ':
            contexts.clear()
            get_help(call.message)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            contexts.clear()
            classifier(call)

    # Block 4. Reply to buttons 'Next/Help' displayed after block_3 showing the 1st place among several visited; is executed in cycle
    # on entry - 2 contexts: 'locations_iteration' and {'location_shown': X, 'total_locations': Y}
    # (where X = the serial number of place visited, for eg. 0 - the 1st place, 2 - the 3rd place),
    # on exit:
    # 1) if user clicks 'Yes' and
    # a) if the last place visited is shown - contexts[] is cleared
    # b) if places to show remain - 2 contexts: 'locations_iteration' and {'location_shown': X+1, 'total_locations': Y}
    # 2) button 'Help' or buttons of previous blocks - contexts[] is cleared
    elif 'locations_iteration' in contexts:
        if call.data == 'Next':
            location_shown = 0
            total_locations = 1
            for context in contexts:
                if 'location_shown' in context:
                    location_shown = context['location_shown']
                    total_locations = context['total_locations']
            if total_locations - (location_shown + 1) == 1:
                contexts.clear()
                every_place(call.message.chat.id, OURTRAVELLER, location_shown + 1, False)
                bot.send_message(call.message.chat.id,
                                 'And that\'s all my journey so far ;)\n\nWhat would you like to do next? We can just talk or use this menu:',
                                 reply_markup=chatbot_markup.intro_menu)
            elif total_locations - (location_shown + 1) > 1:
                every_place(call.message.chat.id, OURTRAVELLER, location_shown + 1, True)
                for context in contexts:
                    if 'location_shown' in context:
                        context['location_shown'] += 1
        elif call.data == 'FAQ':
            contexts.clear()
            get_help(call.message)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            contexts.clear()
            classifier(call)

    # Block 5. User clicked button 'You got Teddy?' and was prompted to enter the secret code
    elif 'enters_code' in contexts:
        # If user enters 'Cancel' or smth similar after entering invalid secret_code - update contexts
        if call.data == 'Cancel':
            contexts.clear()
            bot.send_message(call.message.chat.id, 'Ok. What would you like to do next?',
                             reply_markup=chatbot_markup.intro_menu)
        elif call.data == 'Tell your story':
            contexts.clear()
            bot.send_photo(call.message.chat.id, 'https://iuriid.github.io/img/ft-1.jpg',
                           caption='My name is <strong>{}</strong>. I\'m a traveler.\nMy dream is to see the world'.format(
                               OURTRAVELLER), parse_mode='html')
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(call.message.chat.id, 'Do you want to know more about my journey?',
                             reply_markup=chatbot_markup.yes_no_gotteddy_menu)
            contexts.append('if_journey_info_needed')
        elif call.data == 'FAQ':
            contexts.clear()
            get_help(call.message)
        # If user enters whatever else, not == intent 'smalltalk.confirmation.cancel'
        else:
            secret_code_entered = call.message.text
            if secret_code_validation(secret_code_entered, call.message.chat.id):
                bot.send_message(call.message.chat.id, 'Code correct, thanks! Sorry for formalities')
                bot.send_message(call.message.chat.id, 'What to do next:', reply_markup=chatbot_markup.you_got_teddy_menu)

    # Without context - feed callback_data from button to Dialogflow, return result and menu
    else:
        speech = dialogflow(call.data, call.message.chat.id)['speech']
        intent = dialogflow(call.data, call.message.chat.id)['intent']

        # Button 'Help'
        if call.data == 'FAQ':
            get_help(call.message)

        # Button 'Teddy's story'
        elif call.data == 'Tell your story':
            bot.send_photo(call.message.chat.id, 'https://iuriid.github.io/img/ft-1.jpg',
                           caption='My name is <strong>{}</strong>. I\'m a traveler.\nMy dream is to see the world'.format(
                               OURTRAVELLER), parse_mode='html')
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(call.message.chat.id, 'Do you want to know more about my journey?',
                             reply_markup=chatbot_markup.yes_no_gotteddy_menu)
            contexts.append('if_journey_info_needed')

        # Button 'You got Teddy?'
        elif call.data == 'You got fellowtraveler':
            bot.send_message(call.message.chat.id,
                             'Oh, that\'s a tiny adventure and some responsibility;)\nTo proceed please enter the <i>secret code</i> from the toy',
                             parse_mode='html')
            bot.send_photo(call.message.chat.id, 'https://iuriid.github.io/img/ft-3.jpg', reply_markup=chatbot_markup.cancel_help_menu)
            contexts.clear()
            contexts.append('enters_code')

        # Clicks on all other buttons except Help and Teddy's story without context are hadled as text input
        else:
            print('speech: {}'.format(speech))
            bot.send_message(call.message.chat.id, speech)
            time.sleep(SHORT_TIMEOUT)
            bot.send_message(call.message.chat.id, 'What would you like to do next?', reply_markup=chatbot_markup.intro_menu)


################################### 'Custom' handlers END ##################################

####################################### Functions START ####################################

def dialogflow(query, chat_id, lang_code='en'):
    '''
        Function to communicate with Dialogflow for NLP
    '''
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

def travelers_story_intro(chat_id):
    '''
        Traveler presents him/herself, his/her goal and asks if user would like to know more about traveler's journey
    '''
    # Traveler's photo
    bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-1.jpg',
                   caption='My name is <strong>{}</strong>. I\'m a traveler.\nMy dream is to see the world'.format(
                       OURTRAVELLER), parse_mode='html')
    time.sleep(SHORT_TIMEOUT)
    bot.send_message(chat_id, 'Do you want to know more about my journey?',
                     reply_markup=chatbot_markup.yes_no_gotteddy_menu)

def journey_intro(chat_id):
    '''
        Block 1.
        Displays short general 'intro' information about traveller's origin (for eg., 'I came from Cherkasy city,
        Ukraine, from a family with 3 nice small kids'), presents a map with all visited locations with a link to
        web-map and then user has a choice to click 'Next', 'Help' or just to talk about something
    '''
    time.sleep(SHORT_TIMEOUT)
    bot.send_message(chat_id, 'Ok, here is my story')
    time.sleep(MEDIUM_TIMEOUT)
    bot.send_message(chat_id,
                     'I came from <a href="{}">Cherkasy</a> city, Ukraine, from a family with 3 nice small kids'.format(
                         'https://www.google.com/maps/place/Черкассы,+Черкасская+область,+18000/@50.5012899,25.9683426,6z'),
                     parse_mode='html', disable_web_page_preview=True)
    bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-4.jpg')
    time.sleep(LONG_TIMEOUT)
    bot.send_message(chat_id,
                     'So far the map of my journey looks as follows:',
                     parse_mode='html')
    bot.send_chat_action(chat_id, action='upload_photo')
    bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-3.jpg',
                         caption='<a href="{}">Open map in browser</a>'.format(
                             'https://fellowtraveler.club/#journey_map'), parse_mode='html',
                         reply_markup=chatbot_markup.next_or_help_menu)


def journey_begins(chat_id, traveller):
    '''
        Block 2.
        Retrieves journey summary for a given traveller from DB and presents it (depending on quantity of places
        visited, the only one can be also shown or user may be asked if he want's to see the places)
    '''
    client = MongoClient()
    db = client.TeddyGo

    # Message: I've checked in ... places in ... country[ies] (country1 [, country2 etc]) and have been traveling for ... days so far
    tg_functions.summarize_journey(traveller)
    traveller_summary = db.travellers.find_one({'name': traveller})
    print('traveller_summary: {}'.format(traveller_summary))
    total_locations = traveller_summary['total_locations']
    total_countries = traveller_summary['total_countries']
    countries_visited = traveller_summary['countries_visited']
    countries = ', '.join(countries_visited)
    journey_duration = tg_functions.time_passed(traveller)
    if total_countries == 1:
        countries_form = 'country'
    else:
        countries_form = 'countries'
    if journey_duration == 1:
        day_or_days = 'day'
    else:
        day_or_days = 'days'
    speech = 'So far I\'ve checked in <strong>{}</strong> places located in <strong>{}</strong> {} ({}) and have been traveling for <strong>{}</strong> {}.\n\nI covered about ... km it total and currently I\'m nearly .. km from home'.format(
        total_locations, total_countries, countries_form, countries, journey_duration, day_or_days)
    bot.send_message(chat_id, speech, parse_mode='html')
    return total_locations


def the_1st_place(chat_id, traveller, if_to_continue):
    '''
        Block 3 and also inside block 2
        Shows the place our traveller came from. Is used either directly after journey summary (if only 1 or 2 places
        were visited so far) or as the first place in cycle showing all places visited
    '''
    print()
    print('the_1st_place - if_to_continue: {}'.format(if_to_continue))
    client = MongoClient()
    db = client.TeddyGo

    # Message: I started my journey in ... on ...
    the_1st_location = db[traveller].find()[0]
    formatted_address = the_1st_location['formatted_address']
    lat = the_1st_location['latitude']
    long = the_1st_location['longitude']
    start_date = '{}'.format(the_1st_location['_id'].generation_time.date())
    time_passed = tg_functions.time_passed(traveller)
    if time_passed == 1:
        day_or_days = 'day'
    else:
        day_or_days = 'days'
    message1 = '<strong>Place #1</strong>\nI started my journey on {} ({} {} ago) from \n<i>{}</i>'.format(start_date,
                                                                                                           time_passed,
                                                                                                           day_or_days,
                                                                                                           formatted_address)
    bot.send_message(chat_id, message1, parse_mode='html')
    bot.send_location(chat_id, latitude=lat, longitude=long)
    photos = the_1st_location['photos']
    if len(photos) > 0:
        for photo in photos:
            print(photo)
            bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-3.jpg')
            bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-1.jpg')
    author = the_1st_location['author']
    comment = the_1st_location['comment']
    message2 = 'That was the 1st place'
    if comment != '':
        if author == 'Anonymous':
            author = '(who decided to remain anonymous)'
        else:
            author = '<b>{}</b>'.format(author)
        message2 = 'My new friend {} wrote:\n<i>{}</i>'.format(author, comment)
    else:
        if author != 'Anonymous':
            message2 = 'I got acquainted with a new friend - {} :)'.format(author)
    if if_to_continue:
        bot.send_message(chat_id, message2, parse_mode='html', reply_markup=chatbot_markup.next_or_help_menu)
        print('Here')
    else:
        bot.send_message(chat_id, message2, parse_mode='html')
        print('There')


def every_place(chat_id, traveller, location_to_show, if_to_continue):
    '''
        Block 4
        Shows the 2nd and further visited places
    '''
    client = MongoClient()
    db = client.TeddyGo

    # Message: I started my journey in ... on ...
    location = db[traveller].find()[location_to_show]

    formatted_address = location['formatted_address']
    lat = location['latitude']
    long = location['longitude']
    location_date = '{}'.format(location['_id'].generation_time.date())
    time_passed = tg_functions.time_passed(traveller)
    message1 = '<strong>Place #{}</strong>\nOn {} ({} days ago) I was in \n<i>{}</i>'.format(location_to_show + 1,
                                                                                             location_date, time_passed,
                                                                                             formatted_address)
    bot.send_message(chat_id, message1, parse_mode='html')
    bot.send_location(chat_id, latitude=lat, longitude=long)
    photos = location['photos']
    if len(photos) > 0:
        for photo in photos:
            print(photo)
            bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-3.jpg')
            bot.send_photo(chat_id, 'https://iuriid.github.io/img/ft-1.jpg')
    author = location['author']
    comment = location['comment']
    message2 = 'That was the place #{}'.format(location_to_show + 1)
    if comment != '':
        if author == 'Anonymous':
            author = '(who decided to remain anonymous)'
        else:
            author = '<b>{}</b>'.format(author)
        message2 = 'My new friend {} wrote:\n<i>{}</i>'.format(author, comment)
    else:
        if author != 'Anonymous':
            message2 = 'I got acquainted with a new friend - {} :)'.format(author)
    if if_to_continue:
        bot.send_message(chat_id, message2, parse_mode='html', reply_markup=chatbot_markup.next_or_help_menu)
    else:
        bot.send_message(chat_id, message2, parse_mode='html')


def get_help(message):
    '''
        Displays FAQ/help
    '''
    contexts.clear()
    bot.send_message(message.chat.id, 'Here\'s our FAQ')
    bot.send_message(message.chat.id, 'What would you like to do next?',
                     reply_markup=chatbot_markup.intro_menu)


def secret_code_validation(secret_code_entered, chat_id):
    '''
        Validates the secret code entered by user against the one in DB
        If code valid - updates contexts (remove 'enters_code', append 'code_correct')
        If code invalid - suggests to enter it again + inline button 'Cancel' (to remove context 'enters_code')
    '''
    client = MongoClient()
    db = client.TeddyGo
    collection_travellers = db.travellers
    teddys_sc_should_be = collection_travellers.find_one({"name": OURTRAVELLER})['secret_code']
    if not sha256_crypt.verify(secret_code_entered, teddys_sc_should_be):
        return False
    else:
        return True


####################################### Functions END ####################################


try:
    bot.polling(none_stop=True, timeout=1)
except Exception as e:
    print('Exception: {}'.format(e))
    time.sleep(MEDIUM_TIMEOUT)

# Run Flask server
# if __name__ == '__main__':
#    app.run()
