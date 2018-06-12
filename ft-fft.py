# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '../ft')

import os
import datetime
from datetime import timezone
from flask import Flask, render_template, url_for, request, redirect, flash, session, make_response, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, URL, Email, Optional, EqualTo
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from flask_wtf.recaptcha import RecaptchaField
from flask_mail import Mail, Message
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from flask_jsglue import JSGlue
from flask_googlemaps import GoogleMaps
from flask_googlemaps import Map
from flask_babel import Babel, gettext, lazy_gettext
from functools import wraps
import twitter
import uuid
import requests, json
import facebook

import time
import random
from translations import L10N

from keys import (FLASK_SECRET_KEY,
                  RECAPTCHA_PRIVATE_KEY,
                  RECAPTCHA_PUBLIC_KEY,
                  GOOGLE_MAPS_API_KEY,
                  TWITTER_CONSUMER_KEY,
                  TWITTER_CONSUMER_SECRET,
                  TWITTER_ACCESS_TOKEN_KEY,
                  TWITTER_ACCESS_TOKEN_SECRET,
                  MAIL_PWD,
                  FB_ACCESS_TOKEN,
                  FB_VERIFY_TOKEN,
                  DF_TOKEN)

import ft_functions

SITE_URL = 'https://fellowtraveler.club'
FROM_EMAIL = 'mailvulgaris@gmail.com'
BASIC_TRAVELER = 'Teddy' # 'All'
ALL_TAVELERS = ['Teddy']
PHOTO_DIR = '/static/uploads/' # where photos from places visited are saved
LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'de': 'Deutsch',
    'fr': 'Français',
    'uk': 'Українська'
}

OURTRAVELLER = 'Teddy'
PHOTO_DIR_FFT = '../ft/static/uploads/{}/'.format(OURTRAVELLER) # where photos from places visited are saved
DOMAIN = 'http://fellowtraveler.club'
PHOTO_DIR_OUT = '{}/static/uploads/{}/'.format(DOMAIN, OURTRAVELLER) # where photos from places visited are saved
SERVICE_IMG_DIR = '{}/static/uploads/{}/service/'.format(DOMAIN, OURTRAVELLER) # where 'general info' images are (summary map, secret code example etc)
SHORT_TIMEOUT = 0  # 2 # seconds, between messages for imitation of 'live' typing
MEDIUM_TIMEOUT = 0  # 4
LONG_TIMEOUT = 0  # 6
SUPPORT_EMAIL = 'iurii.dziuban@gmail.com'
USER_LANGUAGE = 'en'
LAST_COMMAND = ''

CONTEXTS = []   # holds last state
NEWLOCATION = {    # holds data for traveler's location before storing it to DB
    'author': None,
    'channel': 'Facebook',
    'user_id_on_channel': None,
    'longitude': None,
    'latitude': None,
    'formatted_address': None,
    'locality': None,
    'administrative_area_level_1': None,
    'country': None,
    'place_id': None,
    'comment': None,
    'photos': [],
    'photos_FB_ids': [],
    'photos_TG_ids': []
}

app = Flask(__name__)
app.config.from_object(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 20 # max photo to upload is 20Mb
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY
GoogleMaps(app, key=GOOGLE_MAPS_API_KEY)
graph = facebook.GraphAPI(access_token=FB_ACCESS_TOKEN, version="2.2")
jsglue = JSGlue(app)
babel = Babel(app)
twitter_api = twitter.Api(
    consumer_key = TWITTER_CONSUMER_KEY,
    consumer_secret = TWITTER_CONSUMER_SECRET,
    access_token_key = TWITTER_ACCESS_TOKEN_KEY,
    access_token_secret = TWITTER_ACCESS_TOKEN_SECRET
)

# Flask-mail configuration
mail = Mail(app)
app.config.update(
    DEBUG=True,
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_SSL=False,
    MAIL_USE_TLS=True,
    MAIL_USERNAME = 'mailvulgaris@gmail.com',
    MAIL_PASSWORD = MAIL_PWD
)
mail = Mail(app)


class WhereisTeddyNow(FlaskForm):
    author = StringField(lazy_gettext('Your name'), validators=[Length(-1, 50, lazy_gettext('Your name is too long (50 characters max)'))])
    comment = TextAreaField(lazy_gettext('Add a comment'), validators=[Length(-1, 280, lazy_gettext('Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters'))])
    getupdatesbyemail = BooleanField(lazy_gettext('Get updates by email'))
    secret_code = PasswordField(lazy_gettext('Secret code from the toy (required)'), validators=[DataRequired(lazy_gettext('Please enter the code which you can find on the toy')),
                              Length(4, 4, lazy_gettext('Secret code must have 4 digits'))])
    recaptcha = RecaptchaField()
    location_submit = SubmitField(lazy_gettext('Submit'))

class RegistrationForm(FlaskForm):
    email = StringField(lazy_gettext('Email Address'), validators=[Length(6, 50), DataRequired(), Email(lazy_gettext('Please enter a valid e-mail address'))])
    password = PasswordField(lazy_gettext('New Password'), validators=[DataRequired(), EqualTo('confirm', message=lazy_gettext('Passwords must match'))])
    confirm = PasswordField(lazy_gettext('Repeat Password'))
    register_submit = SubmitField(lazy_gettext('Register'))

class LoginForm(FlaskForm):
    email = StringField(lazy_gettext('Email Address'), validators=[Length(6, 50), DataRequired(), Email(lazy_gettext('Please enter a valid e-mail address'))])
    password = PasswordField(lazy_gettext('Password'), validators=[DataRequired()])
    login_submit = SubmitField(lazy_gettext('Log in'))

class HeaderEmailSubscription(FlaskForm):
    email4updates = StringField(lazy_gettext('Get updates by email:'), validators=[Optional(), Email(lazy_gettext('Please enter a valid e-mail address'))])
    email_submit = SubmitField(lazy_gettext('Subscribe'))


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'LoggedIn' in session:
            return f(*args, **kwargs)
        else:
            flash(lazy_gettext('You need to <a href="../service/login/">log in</a> first'),'header')
            return redirect(url_for('login'))
    return wrap


def notloggedin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'LoggedIn' in session:
            flash(lazy_gettext('You need to <a href="../service/logout/">log out</a> first'), 'header')
            return redirect(url_for('traveler'))
        else:
            return f(*args, **kwargs)
    return wrap


def send_mail(topic='', recipients=[], message='', sender=FROM_EMAIL):
    '''
    Sends an email using flask-mail
    '''
    try:
        msg = Message(topic, sender=sender, recipients=recipients)
        msg.html = message
        mail.send(msg)
        return True
    except Exception as e:
        print('send_mail() exception: {}'.format(e))
        return False

def save_user_as_subscriber(email_entered, OURTRAVELER):
    '''
        If a registered user (with already verified email) submits a new location with 'Get email updates' checkbox checked,
        add his/her email to subscribers collection. No verification is needed. Flash corresponding message to user
    '''
    try:
        # Check if user's email is not already in DB
        # In rare cases user might subscribe 1st (and verify email or not) and then register to add locations
        user_locale = get_locale()
        userid = str(uuid.uuid4())

        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one({"email": email_entered})

        if email_already_submitted:
            # Update it as verified (it has been verified during registration) and not unsubscribed
            update_subscription = {
                "verified": True,
                "unsubscribed": False,
                "locale": user_locale
            }
            subscribers.update_one({'email': email_entered}, {'$set': update_subscription})
            flash(lazy_gettext("Email {} is already subscribed for updates".format(email_entered)), 'header')
        else:
            # A registered user (with verified email) wants to get email updates
            new_subscriber = {
                "email": email_entered,
                "locale": user_locale,
                "verified": True,
                "verification_code": sha256_crypt.encrypt(userid),
                "unsubscribed": None,
                'which_traveler': OURTRAVELER
            }

            unsubscription_link = '{}/unsubscribe/{}/{}'.format(SITE_URL, email_entered, userid)

            new_subscriber_id = subscribers.insert_one(new_subscriber).inserted_id

            # Send user a confirmation email
            topic = gettext("Fellowtraveler.club: you subscribed to email updates")
            recipients = [email_entered]
            message = gettext("Hi!<br><br>Thanks for subscribing to {0}'s location updates!<br>They won't be too often (not more than once a week).<br><br>If for any reason later you will decide to unsubscribe, please click on the following link:<br><a href='{1}' target='_blank'>{1}</a>").format(OURTRAVELER, unsubscription_link)
            send_mail(topic=topic, recipients=recipients, message=message)

            flash(lazy_gettext("Your email {} was subscribed to {}\'s location updates".format(email_entered, OURTRAVELER)), 'header')
            return {"status": "success",
                "message": "Your email {} was subscribed to Teddy\'s location updates".format(email_entered)}
    except Exception as error:
        flash(lazy_gettext("Error happened ('{}')".format(error)), 'header')
        return {"status": "error",
                "message": "Error happened ('{}')".format(error)}


def save_subscriber(email_entered, OURTRAVELER):
    '''
        Gets email address, checks if it's not already in subscribers' DB, saves it, sends a verification email and informs user with flashes
    '''
    try:
        # Check if user's email is not already in DB
        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one({"$and": [{"email": email_entered}, {'unsubscribed': {'$ne': True}}]})

        if email_already_submitted:
            if email_already_submitted['verified']:
                flash(lazy_gettext("Email {} is already subscribed and verified".format(email_entered)), 'header')
                return {"status": "error", "message": "Email {} is already subscribed and verified".format(email_entered)}
            else:
                flash(lazy_gettext("Email {} is already subscribed but has not been verified yet".format(email_entered)), 'header')
                return {"status": "error",
                        "message": "Email {} is already subscribed but has not been verified yet".format(email_entered)}

        user_locale = get_locale()

        userid = str(uuid.uuid4())

        new_subscriber = {
            "email": email_entered,
            "locale": user_locale,
            "verified": False,
            "verification_code": sha256_crypt.encrypt(userid),
            "unsubscribed": None,
            'which_traveler': OURTRAVELER
        }

        verification_link = '{}/verify/{}/{}'.format(SITE_URL, email_entered, userid)
        unsubscription_link = '{}/unsubscribe/{}/{}'.format(SITE_URL, email_entered, userid)
        print("verification_link: {}".format(verification_link))

        new_subscriber_id = subscribers.insert_one(new_subscriber).inserted_id
        print('new_subscriber_id: {}'.format(new_subscriber_id))

        # Send user a confirmation email with unsubscription link
        topic = gettext("Fellowtraveler.club: email verification link")
        recipients = [email_entered]
        if OURTRAVELER == 'All':
            whos_location_updates = "our travelers'"
        else:
            whos_location_updates = "{}'s".format(OURTRAVELER)

        message = gettext("Hi!<br><br>Thanks for subscribing to {0} location updates!<br>They won't be too often (not more than once a week).<br><br>Please verify your email address by clicking on the following link:<br><b><a href='{1}' target='_blank'>{1}</a></b><br><br>If for any reason later you will decide to unsubscribe, please click on the following link:<br><a href='{2}' target='_blank'>{2}</a>").format(whos_location_updates, verification_link, unsubscription_link)
        send_mail(topic=topic, recipients=recipients, message=message)
        print('message sent')

        flash(lazy_gettext("A verification link has been sent to your email address. Please click on it to verify your email"), 'header')
        return {"status": "success",
                "message": "A verification link has been sent to your email address. Please click on it to verify your email"}
    except Exception as error:
        flash(lazy_gettext("Error happened ('{}')".format(error)), 'header')
        return {"status": "error",
                "message": "Error happened ('{}')".format(error)}


########################################## Functions START ######################################


def get_language(user_id):
    '''
        Retrieves user locale using Facebook Graph API for a user with user_id
    '''
    locale = graph.get_object(id=str(user_id), fields='locale') # {'id': '19xxxxxxxxxxx052', 'locale': 'en_GB'}
    language = 'en'
    if locale.get('locale'):
        if locale.get('locale') == 'uk_UA':
            language = 'uk'
        elif locale.get('locale') == 'ru_RU':
            language = 'ru'
    return language


def get_user_first_name(user_id):
    '''
        Retrieves user first name using Facebook Graph API for a user with user_id
    '''
    user = graph.get_object(id=str(user_id))
    if user.get('first_name'):
        return user.get('first_name')
    else:
        return False


def sender_action(user_id, action_type):
    '''
    Displaying a Sender Action (mark_seen, typing_on, typing_off) to FB user with user_id
    '''
    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'sender_action': 'typing_on'
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def send_message(user_id, our_message):
    '''
    Sends a our_message to FB user with recipient_id
    '''
    #sender_action(user_id, 'typing_off')
    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'message': our_message
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def send_text_message(user_id, text):
    '''
    Sends a text message (text) to FB user with recipient_id
    '''
    #sender_action(user_id, 'typing_off')
    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'message': {'text': text}
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def send_media_template_message(user_id, attachment_id):
    '''
    Sends an image by attachment_id to FB user with user_id
    '''
    #sender_action(user_id, 'typing_off')
    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'message': {
                                    'attachment': {
                                        'type': 'template',
                                        'payload': {
                                        'template_type': 'media',
                                            'elements': [
                                                {
                                                    'media_type': 'image',
                                                    'attachment_id': str(attachment_id)
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def send_text_message_share_location(user_id, text):
    '''
    Sends a text message (text) to FB user with user_id with a quick reply button for sharing location
    '''
    #sender_action(user_id, 'typing_off')
    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'message': {
                                    'text': text,
                                'quick_replies': [
                                    {
                                        'content_type': 'location'
                                    }
                                ]
                                }
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def send_generic_template_message(user_id, title, subtitle='', image_url='', buttons=[]):
    '''
    Sends a generic message (with title, subtitle[optional], image uploaded from url[optional] and up to 3 buttons)
    to FB user with recipient_id
    Buttons of 'postback' type, title=payload
    '''
    #sender_action(user_id, 'typing_off')
    our_buttons = []
    for button in buttons:
        if 'type' not in button:
            our_buttons.append(
                {
                    'type': 'postback',
                    'title': button['title'],
                    'payload': button['payload']
                }
            )
        else:
            our_buttons.append(
                {
                    'type': 'web_url',
                    'url': button['url'],
                    'title': button['title']
                }
        )

    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'message': {
                                    'attachment': {
                                        'type': 'template',
                                        'payload': {
                                            'template_type': 'generic',
                                            'elements': [
                                                {
                                                    'title': title,
                                                    'image_url': image_url,
                                                    'subtitle': subtitle,
                                                    'buttons': our_buttons
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def send_button_template_message(user_id, text, buttons=[]):
    '''
    Sends a button template message (text + up to 3 buttons) to FB user with recipient_id
    Using buttons of 'postback'(by default) or URL type (if 'type': 'url' was indicated)
    '''
    #sender_action(user_id, 'typing_off')
    our_buttons = []
    for button in buttons:
        if 'type' not in button:
            our_buttons.append(
                {
                    'type': 'postback',
                    'title': button['title'],
                    'payload': button['payload']
                }
            )
        else:
            our_buttons.append(
                {
                    'type': 'web_url',
                    'url': button['url'],
                    'title': button['title']
                }
        )

    r = requests.post('https://graph.facebook.com/v2.6/me/messages',
                        params = {'access_token': FB_ACCESS_TOKEN},
                        data = json.dumps(
                            {
                                'recipient': {'id': user_id},
                                'message': {
                                    'attachment': {
                                        'type': 'template',
                                        'payload': {
                                            'template_type': 'button',
                                            'text': text,
                                            'buttons': our_buttons
                                        }
                                    }
                                }
                            }
                        ),
                        headers={'Content-type': 'application/json'}
                      )
    if r.status_code != requests.codes.ok:
        print(r.text)


def travelers_story_intro(user_id):
    '''
        Traveler presents him/herself, his/her goal and asks if user would like to know more about traveler's journey
    '''
    # Traveler's photo
    traveler_photo = SERVICE_IMG_DIR + OURTRAVELLER + '.jpg'

    # message57 = 'My name is'
    # message58 = 'I\'m a traveler.\nMy dream is to see the world'
    message1 = '{} {}. {}'.format(L10N['message57'][USER_LANGUAGE], OURTRAVELLER, L10N['message58'][USER_LANGUAGE])

    # message100 = 'Is English Ok? You also can switch language in Menu>FAQ/Settings>Change language'
    message2 = L10N['message100'][USER_LANGUAGE]

    send_generic_template_message(user_id,
                                    title=message1,
                                    subtitle=message2,
                                    image_url=traveler_photo,
                                    buttons=[
                                        {
                                           # message83 = "Change language"
                                           'title': L10N['message83'][USER_LANGUAGE],
                                           'payload': 'CHANGE_LANGUAGE'
                                        }
                                    ]
                                  )
    time.sleep(SHORT_TIMEOUT)

    # message59 = 'Do you want to know more about my journey?'
    message3 = L10N['message59'][USER_LANGUAGE]

    send_button_template_message(user_id, text=message3, buttons=[
        {
            # message47 = "Yes"
            'title': L10N['message47'][USER_LANGUAGE],
            'payload': L10N['message47'][USER_LANGUAGE]
        },
        {
            # message48 = "No, thanks"
            'title': L10N['message48'][USER_LANGUAGE],
            'payload': L10N['message48'][USER_LANGUAGE]
        },
        {
            # message46 = "You got"
            'title': "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
            # message85 = "You got fellowtraveler"
            'payload': L10N['message85'][USER_LANGUAGE]
        }
    ])


def get_help(user_id):
    '''
        Displays FAQ/help
    '''
    global CONTEXTS

    CONTEXTS.clear()
    # message80 = 'Here\'s our FAQ'
    send_text_message(user_id, L10N['message80'][USER_LANGUAGE])


    send_button_template_message(user_id,
                                 # message8 = 'What would you like to do next?
                                 text=L10N['message8'][USER_LANGUAGE],
                                 buttons=[
        {
            # message84 = "Tell your story"
            "title": L10N['message84'][USER_LANGUAGE],
            "payload": L10N['message84'][USER_LANGUAGE]
        },
        {
            # message46 = "You got"
            # message85 = "You got fellowtraveler"
            "title": '{} {}?'.format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
            "payload": L10N['message85'][USER_LANGUAGE]
        }
    ])


def getting_started(user_id):
    '''
        User clicks either 'Getting started' button when launching the bot or button 'Start' from Persistent menu
    '''
    global CONTEXTS
    global USER_LANGUAGE

    print('CONTEXTS at function entry: {}'.format(CONTEXTS))
    # A fix intended not to respond to every image uploaded (if several)
    ##respond_to_several_photos_only_once()

    # Get user language from message
    if not USER_LANGUAGE:
        USER_LANGUAGE = get_language(user_id)

    if 'if_journey_info_needed' not in CONTEXTS:
        CONTEXTS.clear()

        first_name = get_user_first_name(user_id)
        user_name = ''
        if first_name:
            user_name = ', {}'.format(first_name)

        # message0 = 'Hello'
        message = '{}{}!'.format(L10N['message0'][USER_LANGUAGE], user_name)
        send_text_message(user_id, message)
        CONTEXTS.append('if_journey_info_needed')
        time.sleep(SHORT_TIMEOUT)

    travelers_story_intro(user_id)

    # Console logging
    print()
    print('User clicked button "Start" in Persistent menu')
    print('Contexts at function exit: {}'.format(CONTEXTS))


def help(user_id):
    '''
        User clicks button 'Help/Settings' >> 'Get help' in Persistent menu
    '''
    global CONTEXTS
    print('CONTEXTS at function entry: {}'.format(CONTEXTS))
    # A fix intended not to respond to every image uploaded (if several)
    ##respond_to_several_photos_only_once()

    get_help(user_id)

    # Console logging
    print()
    print('User clicked "Help/Settings >> Get help" in Persistent menu')
    print('Contexts at function exit: {}'.format(CONTEXTS))


def you_got_fellowtraveler(user_id):
    '''
        User clicked button 'If you got a fellow traveler' in Persistent menu
    '''
    global CONTEXTS
    # A fix intended not to respond to every image uploaded (if several)
    ##respond_to_several_photos_only_once()

    if 'code_correct' not in CONTEXTS:
        # message1 = 'Congratulations! That\'s a tiny adventure and some responsibility ;)'
        message1 = L10N['message1'][USER_LANGUAGE]
        send_text_message(user_id, message1)

        # message60 = 'To proceed please enter the secret code from the toy'
        message2 = L10N['message60'][USER_LANGUAGE]
        secret_code_img = SERVICE_IMG_DIR + 'how_secret_code_looks_like.jpg'
        send_generic_template_message(user_id,
                                      title=message2,
                                      image_url=secret_code_img,
                                      buttons=[
                                          {
                                              # message50 = "Cancel"
                                              "title": L10N['message50'][USER_LANGUAGE],
                                              "payload": L10N['message50'][USER_LANGUAGE]
                                          },
                                          {
                                              # message45 = "FAQ"
                                              "title": L10N['message45'][USER_LANGUAGE],
                                              "payload": L10N['message45'][USER_LANGUAGE]
                                          },
                                          {
                                              # message51 = "Contact support"
                                              "title": L10N['message51'][USER_LANGUAGE],
                                              "payload": L10N['message51'][USER_LANGUAGE]
                                          }
                                      ]
                                      )

    else:
        # message6 = 'Ok'
        # message8 = 'What would you like to do next?'
        message3 = '{}. {}'.format(L10N['message6'][USER_LANGUAGE], L10N['message8'][USER_LANGUAGE])
        send_button_template_message(user_id,
                                     text=message3,
                                     buttons=[
                                         {
                                             # message52 = "Instructions"
                                             "title": L10N['message52'][USER_LANGUAGE],
                                             "payload": L10N['message52'][USER_LANGUAGE]
                                         },
                                         {
                                             # message53 = "Add location"
                                             "title": L10N['message53'][USER_LANGUAGE],
                                             "payload": L10N['message53'][USER_LANGUAGE]
                                         },
                                         {
                                             # message51 = "Contact support"
                                             "title": L10N['message51'][USER_LANGUAGE],
                                             "payload": L10N['message51'][USER_LANGUAGE]
                                         }
                                     ]
                                     )

    # Console logging
    print()
    print('User clicked button "If you got a fellow traveler" in Persistent menu')
    print('Contexts: {}'.format(CONTEXTS))


def change_language(user_id):
    '''
        User clicked button 'Change language' in Persistent menu
    '''
    global USER_LANGUAGE

    if not USER_LANGUAGE:
        USER_LANGUAGE = get_language(user_id)

    # message81 = 'Please select your language'
    message = L10N['message81'][USER_LANGUAGE]
    send_button_template_message(user_id,
                                 text=message,
                                 buttons=[
                                     {
                                         # message86 = 'Change language to English'
                                         "title": 'English',
                                         "payload": L10N['message86'][USER_LANGUAGE]
                                     },
                                     {
                                         # message87 = 'Change language to Russian'
                                         "title": 'Русский',
                                         "payload": L10N['message87'][USER_LANGUAGE]
                                     },
                                     {
                                         # message88 = 'Change language to Ukrainian'
                                         "title": 'Українська',
                                         "payload": L10N['message88'][USER_LANGUAGE]
                                     }
                                 ]
                                 )

    print()
    print('User entered "/change_language"')
    print('Contexts: {}'.format(CONTEXTS))


def text_handler(user_id, from_user, message):
    '''
        Handling all text input (NLP using Dialogflow and then depending on recognised intent and contexts variable
    '''
    global CONTEXTS
    global USER_LANGUAGE
    # A fix intended not to respond to every image uploaded (if several)
    ##respond_to_several_photos_only_once()

    # Get input data
    users_input = message
    chat_id = user_id

    if USER_LANGUAGE == None:
        USER_LANGUAGE = get_language(user_id)

    # And pass it to the main handler function [main_hadler()]
    main_handler(users_input, chat_id, from_user, is_btn_click=False, geodata=None, media=False, other_input=False)


def button_click_handler(user_id, from_user, button_payload):
    '''
        Handling clicks on buttons (except for Persistent menu and 'Getting started')

        All possible buttons (10)
        Yes | No, thanks | Cancel | Help | You got Teddy? | Teddy's story | Next | Contact support | Instructions | Add location
        Buttons | Instructions | Add location | are available only after entering secret code
        Buttons | You got Teddy? | Teddy's story | Help | Contact Support | are activated irrespective of context,
        Buttons | Instructions | Add location | are activated always in context 'code_correct',
        other buttons ( Yes | No, thanks | Cancel | Next) - depend on context, if contexts==[] or irrelevant context - they
        should return a response for a Fallback_Intent
    '''
    global CONTEXTS
    global USER_LANGUAGE
    # A fix intended not to respond to every image uploaded (if several)
    #respond_to_several_photos_only_once()

    # Get input data
    users_input = button_payload
    chat_id = user_id

    # Get user language from message
    if not USER_LANGUAGE:
        USER_LANGUAGE = get_language(user_id)

    # And pass it to the main handler function [main_hadler()]
    main_handler(users_input, chat_id, from_user, is_btn_click=True, geodata=None, media=False, other_input=False)


def location_handler(user_id, from_user, lat, long):
    '''
        Handling location input
    '''
    global CONTEXTS
    global NEWLOCATION
    global USER_LANGUAGE
    # A fix intended not to respond to every image uploaded (if several)
    #respond_to_several_photos_only_once()

    # Get input data
    users_input = 'User posted location'
    chat_id = user_id

    if USER_LANGUAGE == None:
        USER_LANGUAGE = USER_LANGUAGE = get_language(user_id)

    # And pass it to the main handler function [main_hadler()]
    main_handler(users_input, chat_id, from_user, is_btn_click=False, geodata={'lat': lat, 'lng': long}, media=False, other_input=False)


def photo_handler(user_id, from_user, img_url):
    '''
        Looks like in FB as distinct from Telegram several images sent by user come in one message (though in separate
        dictionaries inside of entry[x].messaging[y].message.attachments[...]
    '''
    global NEWLOCATION
    global CONTEXTS
    global USER_LANGUAGE

    # Get input data
    chat_id = user_id

    if USER_LANGUAGE == None:
        USER_LANGUAGE = get_language(user_id)

    # Get, save photos, add paths to NEWLOCATION['photos]
    if 'media_input' in CONTEXTS:
        # https://scontent.xx.fbcdn.net/v/t1.15752-9/34416397_446356285788138_8430653788502622208_n.jpg?_nc_cat=0&_nc_ad=z-m&_nc_cid=0&oh=c7c985bab096d0646ea5333064ff6651&oe=5B7F0DD6
        file_name_wo_extension = 'fellowtravelerclub-{}'.format(OURTRAVELLER)
        img_url_part1 = img_url.split('?_nc_cat')[0]
        file_extension = img_url_part1.split('.')[-1]
        current_datetime = datetime.datetime.now().strftime("%d%m%y%H%M%S")
        random_int = random.randint(100, 999)
        path4db = file_name_wo_extension + '-' + current_datetime + str(random_int) + file_extension
        path = PHOTO_DIR + path4db

        r = requests.get(img_url, timeout=0.5)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
        NEWLOCATION['photos'].append(path4db)
        users_input = 'User posted a photo'

        # Contexts - indicate that last input was an image
        if 'last_input_media' not in CONTEXTS:
            CONTEXTS.append('last_input_media')
            users_input = 'User uploaded an image'
            main_handler(users_input, chat_id, from_user, is_btn_click=False, geodata=None, media=True,
                         other_input=False)
    else:
        if 'last_input_media' not in CONTEXTS:
            CONTEXTS.append('last_input_media')
            users_input = 'Nice image ;)'
            print('Really true!')
            print('CONTEXTS: {}'.format(CONTEXTS))
            main_handler(users_input, chat_id, from_user, is_btn_click=False, geodata=None, media=True, other_input=False)


def other_content_types_handler(user_id, from_user):
    '''
        Handling other content types (audio, file, stickers (as images but with field 'sticker_id')
    '''
    global CONTEXTS
    global NEWLOCATION
    global USER_LANGUAGE
    # A fix intended not to respond to every image uploaded (if several)
    #respond_to_several_photos_only_once()

    # Get input data
    users_input = ';)'  # User entered something different from text, button_click, photo or location
    chat_id = user_id

    if USER_LANGUAGE == None:
        USER_LANGUAGE = get_language(user_id)

    # And pass it to the main handler function [main_hadler()]
    main_handler(users_input, chat_id, from_user, is_btn_click=False, geodata=None, media=False,
                 other_input=True)


def dialogflow(query, user_id, lang_code='en'):
    '''
        Function to communicate with Dialogflow for NLU
    '''
    URL = 'https://api.dialogflow.com/v1/query?v=20170712'
    print('USER_LANGUAGE: ' + lang_code)
    HEADERS = {'Authorization': 'Bearer ' + DF_TOKEN, 'content-type': 'application/json'}
    payload = {'query': query, 'sessionId': user_id, 'lang': USER_LANGUAGE}
    r = requests.post(URL, data=json.dumps(payload), headers=HEADERS).json()
    #print('#####')
    #print('Request from DF: ')
    #print(r)
    #print('#####')
    intent = r.get('result').get('metadata').get('intentName')
    speech = r.get('result').get('fulfillment').get('speech')
    status = r.get('status').get('code')
    output = {
        'status': status,
        'intent': intent,
        'speech': speech
    }
    print('\nUSER SAID:')
    print(query)
    print('DIALOGFLOWs OUTPUT:')
    print('-- intent: {}'.format(intent))
    print('-- speech: {}'.format(speech))
    print('CONTEXTS: {}'.format(CONTEXTS))
    return output


def send_email(from_user_id, users_input):
    '''
        Sends email to SUPPORT_EMAIL (iurii.dziuban@gmail.com) from user with ID 'from_user_id with message
        'users_input'
    '''
    with app.app_context():
        try:
            msg = Message("Fellowtraveler.club - message from Facebook user #{}".format(from_user_id),
                          sender="mailvulgaris@gmail.com", recipients=[SUPPORT_EMAIL])
            msg.html = "Facebook user ID<b>{}</b> wrote:<br><i>{}</i>".format(from_user_id, users_input)
            mail.send(msg)
            return True
        except Exception as e:
            print('send_email() exception: {}'.format(e))
            return False


def always_triggered(chat_id, intent, speech):
    '''
        Buttons | You got Teddy? | Teddy's story | Help | are activated always, irrespective of context
        Buttons | Instructions | Add location | are activated always in context 'code_correct'
    '''
    global CONTEXTS
    global USER_LANGUAGE

    # User typed 'Help' or similar
    if intent == 'show_faq':
        get_help(chat_id)
        return True

    # User typed 'Teddy's story' or similar
    elif intent == 'tell_your_story':
        # Traveler's photo
        traveler_photo = SERVICE_IMG_DIR + OURTRAVELLER + '.jpg'

        # message57 = 'My name is'
        # message58 = 'I\'m a traveler.\nMy dream is to see the world'
        message1 = '{} {}. {}'.format(L10N['message57'][USER_LANGUAGE], OURTRAVELLER, L10N['message58'][USER_LANGUAGE])

        # message59 = 'Do you want to know more about my journey?'
        message2 = L10N['message59'][USER_LANGUAGE]

        send_generic_template_message(chat_id,
                                      title=message1,
                                      subtitle=message2,
                                      image_url=traveler_photo,
                                      buttons=[
                                          {
                                              # message47 = "Yes"
                                              'title': L10N['message47'][USER_LANGUAGE],
                                              'payload': L10N['message47'][USER_LANGUAGE]
                                          },
                                          {
                                              # message48 = "No, thanks"
                                              'title': L10N['message48'][USER_LANGUAGE],
                                              'payload': L10N['message48'][USER_LANGUAGE]
                                          },
                                          {
                                              # message46 = "You got"
                                              'title': "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                                              'payload': L10N['message85'][USER_LANGUAGE]
                                          }
                                      ]
                                      )


        if 'if_journey_info_needed' not in CONTEXTS:
            CONTEXTS.append('if_journey_info_needed')
        return True

    # User typed "You got Teddy" or similar
    elif intent == 'you_got_fellowtraveler':
        if 'code_correct' not in CONTEXTS:
            # message1 = 'Congratulations! That\'s a tiny adventure and some responsibility ;)'
            message1 = L10N['message1'][USER_LANGUAGE]
            send_text_message(chat_id, message1)

            # message60 = 'To proceed please enter the secret code from the toy'
            message2 = L10N['message60'][USER_LANGUAGE]
            # Image with an example of secret code
            secret_code_img = SERVICE_IMG_DIR + 'how_secret_code_looks_like.jpg'
            send_generic_template_message(chat_id,
                                          title=message2,
                                          image_url=secret_code_img,
                                          buttons=[
                                              {
                                                  # message50 = "Cancel"
                                                  "title": L10N['message50'][USER_LANGUAGE],
                                                  "payload": L10N['message50'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message45 = "FAQ"
                                                  "title": L10N['message45'][USER_LANGUAGE],
                                                  "payload": L10N['message45'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message51 = "Contact support"
                                                  "title": L10N['message51'][USER_LANGUAGE],
                                                  "payload": L10N['message51'][USER_LANGUAGE]
                                              }
                                          ]
                                          )
            CONTEXTS.clear()
            CONTEXTS.append('enters_code')
        else:
            # message6 = 'Ok'
            # message8 = 'What would you like to do next?'
            message3 = '{}. {}'.format(L10N['message6'][USER_LANGUAGE], L10N['message8'][USER_LANGUAGE])
            send_button_template_message(chat_id,
                                         text=message3,
                                         buttons=[
                                             {
                                                 # message52 = "Instructions"
                                                 "title": L10N['message52'][USER_LANGUAGE],
                                                 "payload": L10N['message52'][USER_LANGUAGE]
                                             },
                                             {
                                                 # message53 = "Add location"
                                                 "title": L10N['message53'][USER_LANGUAGE],
                                                 "payload": L10N['message53'][USER_LANGUAGE]
                                             },
                                             {
                                                 # message51 = "Contact support"
                                                 "title": L10N['message51'][USER_LANGUAGE],
                                                 "payload": L10N['message51'][USER_LANGUAGE]
                                             }
                                         ]
                                         )
        return True

    # User clicks/types "Contact support"
    elif intent == 'contact_support':
        if 'contact_support' not in CONTEXTS:
            CONTEXTS.append('contact_support')

            # message17 = 'Any problems, questions, suggestions, remarks, proposals etc? Please enter them below or write to my author\'s email <b>iurii.dziuban@gmail.com</b>\n\n You may also consider visiting <a href="https://iuriid.github.io">iuriid.github.io</a>.'
            message = L10N['message17'][USER_LANGUAGE]
            send_button_template_message(chat_id, text=message,  buttons=[
                                              {
                                                  # message50 = "Cancel"
                                                  "title": L10N['message50'][USER_LANGUAGE],
                                                  "payload": L10N['message50'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message45 = "FAQ"
                                                  "title": L10N['message45'][USER_LANGUAGE],
                                                  "payload": L10N['message45'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message51 = "Contact support"
                                                  "title": L10N['message51'][USER_LANGUAGE],
                                                  "payload": L10N['message51'][USER_LANGUAGE]
                                              }
                                          ])
        return True

    # Switch language buttons
    elif intent == 'change_language':
        # message81 = 'Please select your language'
        message = L10N['message81'][USER_LANGUAGE]
        send_button_template_message(chat_id,
                                     text=message,
                                     buttons=[
                                         {
                                             # message86 = 'Change language to English'
                                             "title": 'English',
                                             "payload": L10N['message86'][USER_LANGUAGE]
                                         },
                                         {
                                             # message87 = 'Change language to Russian'
                                             "title": 'Русский',
                                             "payload": L10N['message87'][USER_LANGUAGE]
                                         },
                                         {
                                             # message88 = 'Change language to Ukrainian'
                                             "title": 'Українська',
                                             "payload": L10N['message88'][USER_LANGUAGE]
                                         }
                                     ]
                                     )

    # Switch to English
    elif intent == 'language_to_english':
        USER_LANGUAGE = 'en'
        # message82 = 'Language was changed to <b>English</b>'
        message = L10N['message82'][USER_LANGUAGE]
        send_button_template_message(chat_id, text=message, buttons=[
            {
                # message84 = "Tell your story"
                "title": L10N['message84'][USER_LANGUAGE],
                "payload": L10N['message84'][USER_LANGUAGE]
            },
            {
                # message45 = "FAQ"
                "title": L10N['message45'][USER_LANGUAGE],
                "payload": L10N['message45'][USER_LANGUAGE]
            },
            {
                # message46 = "You got"
                "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                # message85 = "You got fellowtraveler"
                "payload": L10N['message85'][USER_LANGUAGE]
            }
        ])
        return True

    # Switch to Russian
    elif intent == 'language_to_russian':
        USER_LANGUAGE = 'ru'
        # message82 = 'Язык был изменен на русский'
        message = L10N['message82'][USER_LANGUAGE]
        send_button_template_message(chat_id, text=message, buttons=[
            {
                # message84 = "Tell your story"
                "title": L10N['message84'][USER_LANGUAGE],
                "payload": L10N['message84'][USER_LANGUAGE]
            },
            {
                # message45 = "FAQ"
                "title": L10N['message45'][USER_LANGUAGE],
                "payload": L10N['message45'][USER_LANGUAGE]
            },
            {
                # message46 = "You got"
                "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                # message85 = "You got fellowtraveler"
                "payload": L10N['message85'][USER_LANGUAGE]
            }
        ])
        return True

    # Switch to Ukrainian
    elif intent == 'language_to_ukrainian':
        USER_LANGUAGE = 'uk'
        # message82 = 'Мову було змінено на українську'
        message = L10N['message82'][USER_LANGUAGE]
        send_button_template_message(chat_id, text=message, buttons=[
            {
                # message84 = "Tell your story"
                "title": L10N['message84'][USER_LANGUAGE],
                "payload": L10N['message84'][USER_LANGUAGE]
            },
            {
                # message45 = "FAQ"
                "title": L10N['message45'][USER_LANGUAGE],
                "payload": L10N['message45'][USER_LANGUAGE]
            },
            {
                # message46 = "You got"
                "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                # message85 = "You got fellowtraveler"
                "payload": L10N['message85'][USER_LANGUAGE]
            }
        ])
        return True

    # Buttons | Instructions | Add location | are activated always in context 'code_correct'
    if 'code_correct' in CONTEXTS:
        if intent == 'show_instructions':
            # message21 = 'Here are the detailed instructions for those who got'
            message = '{} {}'.format(L10N['message21'][USER_LANGUAGE], OURTRAVELLER)
            send_button_template_message(chat_id, text=message, buttons=[
                {
                    # message52 = "Instructions"
                    "title": L10N['message52'][USER_LANGUAGE],
                    "payload": L10N['message52'][USER_LANGUAGE]
                },
                {
                    # message53 = "Add location"
                    "title": L10N['message53'][USER_LANGUAGE],
                    "payload": L10N['message53'][USER_LANGUAGE]
                },
                {
                    # message51 = "Contact support"
                    "title": L10N['message51'][USER_LANGUAGE],
                    "payload": L10N['message51'][USER_LANGUAGE]
                }
            ])
            return True

        elif intent == 'add_location':
            # message22 = 'First please tell <i>where</i>'
            # message23 = '<i>is now</i> (you may use the button \"<b>Share your location</b>\" below) \n\nor \n\n<i>where he was</i> photographed (to enter address which differs from your current location please <b>attach >> Location</b> and drag the map to desired place)'
            message = '{} {} {}'.format(L10N['message22'][USER_LANGUAGE], OURTRAVELLER, L10N['message23'][USER_LANGUAGE])
            send_text_message_share_location(chat_id, message)
            if 'location_input' not in CONTEXTS:
                CONTEXTS.append('location_input')
            return True

    else:
        return False


def default_fallback(chat_id, intent, speech):
    '''
        Response for all inputs (manual entry or button clicks) which are irrelevant to current context
    '''
    global CONTEXTS

    code_correct_flag, location_input_flag, last_input_media_flag = False, False, False
    if 'code_correct' in CONTEXTS:
        code_correct_flag = True
    if 'location_input' in CONTEXTS:
        location_input_flag = True
    if 'last_input_media' in CONTEXTS:
        last_input_media_flag = True

    CONTEXTS.clear()

    if code_correct_flag:
        CONTEXTS.append('code_correct')
    if location_input_flag:
        CONTEXTS.append('location_input')
    if last_input_media_flag:
        CONTEXTS.append('last_input_media')

    if intent == 'add_location':
        if 'code_correct' not in CONTEXTS:
            if 'enters_code' not in CONTEXTS:
                CONTEXTS.append('enters_code')


            # message60 = 'To proceed please enter the secret code from the toy'
            message1 = L10N['message60'][USER_LANGUAGE]
            # Image with an example of secret code
            secret_code_img = SERVICE_IMG_DIR + 'how_secret_code_looks_like.jpg'
            send_generic_template_message(chat_id,
                                          title=message1,
                                          image_url=secret_code_img,
                                          buttons=[
                                              {
                                                  # message50 = "Cancel"
                                                  "title": L10N['message50'][USER_LANGUAGE],
                                                  "payload": L10N['message50'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message45 = "FAQ"
                                                  "title": L10N['message45'][USER_LANGUAGE],
                                                  "payload": L10N['message45'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message51 = "Contact support"
                                                  "title": L10N['message51'][USER_LANGUAGE],
                                                  "payload": L10N['message51'][USER_LANGUAGE]
                                              }
                                          ]
                                          )
        else:
            send_text_message(chat_id, speech)
            time.sleep(SHORT_TIMEOUT)

            # message8 = 'What would you like to do next?'
            message3 = '{}. {}'.format(L10N['message6'][USER_LANGUAGE], L10N['message8'][USER_LANGUAGE])
            send_button_template_message(chat_id,
                                         text=message3,
                                         buttons=[
                                             {
                                                 # message52 = "Instructions"
                                                 "title": L10N['message52'][USER_LANGUAGE],
                                                 "payload": L10N['message52'][USER_LANGUAGE]
                                             },
                                             {
                                                 # message53 = "Add location"
                                                 "title": L10N['message53'][USER_LANGUAGE],
                                                 "payload": L10N['message53'][USER_LANGUAGE]
                                             },
                                             {
                                                 # message51 = "Contact support"
                                                 "title": L10N['message51'][USER_LANGUAGE],
                                                 "payload": L10N['message51'][USER_LANGUAGE]
                                             }
                                         ]
                                         )
    else:
        send_text_message(chat_id, speech)
        time.sleep(SHORT_TIMEOUT)

        # message8 = 'What would you like to do next?'
        message3 = '{}. {}'.format(L10N['message6'][USER_LANGUAGE], L10N['message8'][USER_LANGUAGE])
        send_button_template_message(chat_id,
                                     text=message3,
                                     buttons=[
                                         {
                                             # message84 = "Tell your story"
                                             "title": L10N['message84'][USER_LANGUAGE],
                                             "payload": L10N['message84'][USER_LANGUAGE]
                                         },
                                         {
                                             # message45 = "FAQ"
                                             "title": L10N['message45'][USER_LANGUAGE],
                                             "payload": L10N['message45'][USER_LANGUAGE]
                                         },
                                         {
                                             # message46 = "You got"
                                             "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                                             # message85 = "You got fellowtraveler"
                                             "payload": L10N['message85'][USER_LANGUAGE]
                                         }
                                     ]
                                     )


def journey_intro(chat_id, traveller):
    '''
        Displays short general 'intro' information about traveller's origin (for eg., 'I came from Cherkasy city,
        Ukraine, from a family with 3 nice small kids'), generates and presents an image from the map with all
        visited locations with a link to web-map and then user has a choice to click 'Next', 'Help' or just to
        talk about something
    '''
    time.sleep(SHORT_TIMEOUT)
    # message61 = 'Ok, here is my story'
    message1 = L10N['message61'][USER_LANGUAGE]
    send_text_message(chat_id, message1)

    time.sleep(MEDIUM_TIMEOUT)

    if save_static_map(traveller):
        # message62 = 'I came from '
        # message63 = 'Cherkasy city, Ukraine, from a family with 3 nice small kids'
        message2 = '{}{}'.format(L10N['message62'][USER_LANGUAGE], L10N['message63'][USER_LANGUAGE])
        send_text_message(chat_id, message2)

        send_media_template_message(chat_id, '196520410973040') # biography.jpg

        time.sleep(LONG_TIMEOUT)

        # message64 = 'So far the map of my journey looks as follows:'
        message3 = L10N['message64'][USER_LANGUAGE]
        static_summary_map = PHOTO_DIR_OUT + OURTRAVELLER + '_summary_map.png'

        send_generic_template_message(chat_id, title=message3, image_url=static_summary_map, buttons=[
            {
                # message65 = 'Open map in browser'
                'title': L10N['message65'][USER_LANGUAGE],
                'type': 'web_url',
                'url': DOMAIN + '/#journey_map'
            },
            {
                # message49 = "Next"
                "title": L10N['message49'][USER_LANGUAGE],
                "payload": L10N['message49'][USER_LANGUAGE]
            },
            {
                # message45 = "FAQ"
                "title": L10N['message45'][USER_LANGUAGE],
                "payload": L10N['message45'][USER_LANGUAGE]
            }
        ])
    else:
        # message62 = 'I came from '
        # message63 = 'Cherkasy city, Ukraine, from a family with 3 nice small kids'
        message2 = '{}{}'.format(L10N['message62'][USER_LANGUAGE], L10N['message63'][USER_LANGUAGE])
        biography_photo = SERVICE_IMG_DIR + 'biography.jpg'
        send_generic_template_message(chat_id, title=message2, image_url=biography_photo, buttons=[
            {
                # message49 = "Next"
                "title": L10N['message49'][USER_LANGUAGE],
                "payload": L10N['message49'][USER_LANGUAGE]
            },
            {
                # message45 = "FAQ"
                "title": L10N['message45'][USER_LANGUAGE],
                "payload": L10N['message45'][USER_LANGUAGE]
            }
        ])


def save_static_map(traveller):
    '''
    https://developers.google.com/maps/documentation/static-maps/intro
    Requests a list of places visited by traveller from DB and draws a static (png) map
    '''
    #print('\nsave_static_map()')
    try:
        markers = ft_functions.get_location_history(traveller, PHOTO_DIR)['mymarkers'][::-1]
        latlongparams = ''
        for index, marker in enumerate(markers):
            latlongparams += '&markers=color:green%7Clabel:{}%7C{},{}'.format(index + 1, marker['lat'], marker['lng'])
        query = 'https://maps.googleapis.com/maps/api/staticmap?size=700x400&maptype=roadmap{}&key={}'.format(latlongparams, GOOGLE_MAPS_API_KEY)
        #print('query: {}'.format(query))

        path = PHOTO_DIR + traveller + '_summary_map.png'
        #print('path: {}'.format(path))

        r = requests.get(query, timeout=0.5)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)

        return True
    except Exception as e:
        print('save_static_map() exception: {}'.format(e))
        return False


def journey_begins(chat_id, traveller):
    '''
        Block 2.
        Retrieves journey summary for a given traveller from DB and presents it (depending on quantity of places
        visited, the only one can be also shown or user may be asked if he want's to see the places)
    '''
    speech = ''
    total_locations = 0

    travelled_so_far = ft_functions.get_journey_summary(traveller)
    if not travelled_so_far:
        speech = ''
    else:
        total_countries = travelled_so_far['total_countries']
        total_locations = travelled_so_far['total_locations']
        total_distance = travelled_so_far['total_distance']
        journey_duration = travelled_so_far['journey_duration']
        distance_from_home = travelled_so_far['distance_from_home']
        countries_visited_codes = travelled_so_far['countries_visited']
        countries_visited = ft_functions.translate_countries(countries_visited_codes, USER_LANGUAGE)
        countries_list = (', ').join(countries_visited)

        if total_countries == 1:
            # message95 = 'country'
            countries_form = L10N['message95'][USER_LANGUAGE]
        else:
            # message96 = 'countries'
            countries_form = L10N['message96'][USER_LANGUAGE]

        if journey_duration == 1:
            # message97 = 'day'
            day_or_days = L10N['message97'][USER_LANGUAGE]
        else:
            # message98 = 'days'
            day_or_days = L10N['message98'][USER_LANGUAGE]
            # message89 = 'So far I\'ve checked in'
            # message90 = 'places located in'
            # message91 = 'and have been traveling for'
            # message92 = 'I covered about'
            # message93 = 'km it total and currently I\'m nearly'km from home
            # message94 = 'km from home'
            speech = '{} {} {} {} {} ({}) {} {} {}.\n\n' \
                          '{} {} {} {} {}'.format(
                L10N['message89'][USER_LANGUAGE],
            total_locations, L10N['message90'][USER_LANGUAGE], total_countries, countries_form, countries_list, L10N['message91'][USER_LANGUAGE], journey_duration, day_or_days,
                L10N['message92'][USER_LANGUAGE], total_distance, L10N['message93'][USER_LANGUAGE], distance_from_home, L10N['message94'][USER_LANGUAGE])

    send_text_message(chat_id, speech)
    return total_locations


def the_1st_place(chat_id, traveller, if_to_continue):
    '''
        Block 3 and also inside block 2
        Shows the place our traveller came from. Is used either directly after journey summary (if only 1 or 2 places
        were visited so far) or as the first place in cycle showing all places visited
    '''
    #print('the_1st_place - if_to_continue: {}'.format(if_to_continue))
    client = MongoClient()
    db = client.TeddyGo

    # Message: I started my journey in ... on ...
    if db[traveller].find().count() != 0:
        the_1st_location = db[traveller].find()[0]
        formatted_address = the_1st_location['formatted_address']
        lat = the_1st_location['latitude']
        long = the_1st_location['longitude']
        start_date = '{}'.format(the_1st_location['_id'].generation_time.date())
        time_passed = ft_functions.time_passed(traveller)
        if time_passed == 0:
            # message73 = 'today'
            day_or_days = L10N['message73'][USER_LANGUAGE]
        elif time_passed == 1:
            # message74 = '1 day ago'
            day_or_days = L10N['message74'][USER_LANGUAGE]
        else:
            # message75 = 'days ago'
            day_or_days = '{} {}'.format(time_passed, L10N['message75'][USER_LANGUAGE])

        # message66 = '<strong>Place #1</strong>\nI started my journey on'
        # message67 = 'from'
        message1 = '{} {} ({}) {} \n{}'.format(L10N['message66'][USER_LANGUAGE], start_date, day_or_days, L10N['message67'][USER_LANGUAGE], formatted_address)
        send_text_message(chat_id, message1)

        # Sending location as a static GMap in generic template (lat/long as title, url button with link to map)
        message3 = '{}, {}'.format(lat, long)
        map_image = 'https://maps.googleapis.com/maps/api/staticmap?key={}&markers=color:green|{},{}&size=700x400&maptype=roadmap'.format(
            GOOGLE_MAPS_API_KEY, lat, long)
        send_generic_template_message(chat_id,title=message3,image_url=map_image, buttons=[
            {
                # message65 = 'Open map in browser'
                'title': L10N['message65'][USER_LANGUAGE],
                'type': 'web_url',
                'url': 'https://www.google.com/maps/search/?api=1&query={},{}'.format(lat, long)
            }
        ])

        # Sending photos for the place as media templates
        photos = the_1st_location['photos_FB_ids']
        if len(photos) > 0:
            for photo in photos:
                send_media_template_message(chat_id, photo)

        # Sending comment/info about author
        author = the_1st_location['author']
        comment = the_1st_location['comment']
        # message68 = 'That was the 1st place'
        message2 = L10N['message68'][USER_LANGUAGE]
        if comment != '':
            if author == 'Anonymous':
                # message69 = '(who decided to remain anonymous)'
                author = L10N['message69'][USER_LANGUAGE]
            else:
                author = '{}'.format(author)
            # message70 = 'My new friend'
            # message71 = 'wrote:'
            message2 = '{} {} {}\n{}'.format(L10N['message70'][USER_LANGUAGE], author, L10N['message71'][USER_LANGUAGE], comment)
        else:
            if author != 'Anonymous':
                # message72 = 'I got acquainted with a new friend - '
                message2 = '{} {} :)'.format(L10N['message72'][USER_LANGUAGE], author)

        if if_to_continue:
            send_button_template_message(chat_id, text=message2, buttons=[
            {
                # message49 = "Next"
                "title": L10N['message49'][USER_LANGUAGE],
                "payload": L10N['message49'][USER_LANGUAGE]
            },
            {
                # message45 = "FAQ"
                "title": L10N['message45'][USER_LANGUAGE],
                "payload": L10N['message45'][USER_LANGUAGE]
            }
            ])
        else:
            send_text_message(chat_id, message2)
    else:
        pass


def time_from_location(from_date):
    '''
        Function calculates time elapsed from the date when traveler was in specific location (from_date) to now
    '''
    current_datetime = datetime.datetime.now(timezone.utc)
    difference = (current_datetime - from_date).days
    return difference


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
    location_date_service = location['_id'].generation_time
    time_passed = time_from_location(location_date_service)
    if time_passed == 0:
        # message73 = 'today'
        day_or_days = L10N['message73'][USER_LANGUAGE]
    elif time_passed == 1:
        # message74 = '1 day ago'
        day_or_days = L10N['message74'][USER_LANGUAGE]
    else:
        # message75 = 'days ago'
        day_or_days = '{} {}'.format(time_passed, L10N['message75'][USER_LANGUAGE])
    # message76 = 'Place #'
    # message77 = '\nOn'
    # message101 = 'I was here:'
    message1 = '{}{} {} {} ({}) {}'.format(L10N['message76'][USER_LANGUAGE], location_to_show + 1, L10N['message77'][USER_LANGUAGE],
                                                                                             location_date, day_or_days, L10N['message101'][USER_LANGUAGE])
    send_text_message(chat_id, message1)

    # Sending location as a static GMap in generic template (lat/long as title, url button with link to map)
    message3 = formatted_address
    map_image = 'https://maps.googleapis.com/maps/api/staticmap?key={}&markers=color:green|{},{}&size=700x400&maptype=roadmap'.format(
        GOOGLE_MAPS_API_KEY, lat, long)
    send_generic_template_message(chat_id, title=message3, image_url=map_image, buttons=[
        {
            # message65 = 'Open map in browser'
            'title': L10N['message65'][USER_LANGUAGE],
            'type': 'web_url',
            'url': 'https://www.google.com/maps/search/?api=1&query={},{}'.format(lat, long)
        }
    ])

    # Sending photos for the place as media templates
    photos = location['photos_FB_ids']
    if len(photos) > 0:
        for photo in photos:
            send_media_template_message(chat_id, photo)

    # Sending comment/info about author
    author = location['author']
    comment = location['comment']
    # message79 = 'That was the place #'
    message2 = '{}{}'.format(L10N['message79'][USER_LANGUAGE], location_to_show + 1)
    if comment != '':
        if author == 'Anonymous':
            # message69 = '(who decided to remain anonymous)'
            author = L10N['message69'][USER_LANGUAGE]
        else:
            author = '{}'.format(author)

        # message70 = 'My new friend'
        # message71 = 'wrote:'
        message2 = '{} {} {}\n{}'.format(L10N['message70'][USER_LANGUAGE], author, L10N['message71'][USER_LANGUAGE], comment)
    else:
        '''
        if author != 'Anonymous':
            # message72 = 'I got acquainted with a new friend - '
            message2 = '{}{} :)'.format(L10N['message72'][USER_LANGUAGE], author)
        '''
        pass

    if if_to_continue:
        send_button_template_message(chat_id, text=message2, buttons=[
        {
            # message49 = "Next"
            "title": L10N['message49'][USER_LANGUAGE],
            "payload": L10N['message49'][USER_LANGUAGE]
        },
        {
            # message45 = "FAQ"
            "title": L10N['message45'][USER_LANGUAGE],
            "payload": L10N['message45'][USER_LANGUAGE]
        }
        ])
    else:
        send_text_message(chat_id, message2)


def secret_code_validation(secret_code_entered):
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


def gmaps_geocoder(lat, lng):
    '''
    Google Maps - reverse geocoding (https://developers.google.com/maps/documentation/geocoding/start#reverse)
    Getting geodata (namely 'formatted_address', 'locality', 'administrative_area_level_1', 'country' and 'place_id')
    for coordinates received after location sharing in Telegram
    '''
    global NEWLOCATION

    URL = 'https://maps.googleapis.com/maps/api/geocode/json?latlng={},{}&key={}'.format(lat, lng, GOOGLE_MAPS_API_KEY)
    try:
        r = requests.get(URL).json().get('results')

        if r[0]:
            formatted_address = r[0].get('formatted_address')
            address_components = r[0].get('address_components')
            locality, administrative_area_level_1, country, place_id = None, None, None, None
            for address_component in address_components:
                types = address_component.get('types')
                short_name = address_component.get('short_name')
                # print("type: {}, short name: {}".format(types, short_name))
                if 'locality' in types:
                    locality = short_name
                elif 'administrative_area_level_1' in types:
                    administrative_area_level_1 = short_name
                elif 'country' in types:
                    country = short_name
            place_id = r[0].get('place_id')

            NEWLOCATION['formatted_address'] = formatted_address
            NEWLOCATION['locality'] = locality
            NEWLOCATION['administrative_area_level_1'] = administrative_area_level_1
            NEWLOCATION['country'] = country
            NEWLOCATION['place_id'] = place_id

        return True
    except Exception as e:
        print('gmaps_geocoder() exception: {}'.format(e))
        #send_email('Logger', 'gmaps_geocoder() exception: {}'.format(e))
        return False


def new_location_summary(chat_id, from_user):
    '''
        Functions sums up data on new location (held in NEWLOCATION variable) before saving the new location to DB
    '''
    try:
        location_date = datetime.datetime.now().strftime('%Y-%m-%d')
        message1 = 'On {} I ({}) was in \n{}'.format(location_date, OURTRAVELLER, NEWLOCATION['formatted_address'])
        send_text_message(chat_id, message1)

        # Sending location as a static GMap in generic template (lat/long as title, url button with link to map)
        lat = NEWLOCATION['latitude']
        long = NEWLOCATION['longitude']
        message3 = '{}, {}'.format(lat, long)
        map_image = 'https://maps.googleapis.com/maps/api/staticmap?key={}&markers=color:green|{},{}&size=700x400&maptype=roadmap'.format(
            GOOGLE_MAPS_API_KEY, lat, long)
        send_generic_template_message(chat_id,title=message3,image_url=map_image, buttons=[
            {
                # message65 = 'Open map in browser'
                'title': L10N['message65'][USER_LANGUAGE],
                'type': 'web_url',
                'url': 'https://www.google.com/maps/search/?api=1&query={},{}'.format(lat, long)
            }
        ])

        # Sending photos for the place as media templates
        photos = NEWLOCATION['photos_FB_ids']
        if len(photos) > 0:
            for photo in photos:
                send_media_template_message(chat_id, photo)

        author = '{}'.format(from_user)
        comment = NEWLOCATION['comment']
        if comment != '':
            # message70 = 'My new friend'
            # message71 = 'wrote:'
            message2 = '{} {} {}\n{}'.format(L10N['message70'][USER_LANGUAGE], author,
                                                    L10N['message71'][USER_LANGUAGE], comment)
        else:
            # message72 = 'I got acquainted with a new friend - '
            message2 = '{} {} :)'.format(L10N['message72'][USER_LANGUAGE], author)
        send_text_message(chat_id, message2)
        return True
    except Exception as e:
        print('new_location_summary() exception: {}'.format(e))
        return False


def submit_new_location(traveller):
    '''
        Saves new location (NEWLOCATION) to DB
        Updates journey summary
    '''
    global NEWLOCATION
    try:
        # Logging
        print('')
        print('Saving location to DB...')
        #print('NEWLOCATION: {}'.format(NEWLOCATION))

        client = MongoClient()
        db = client.TeddyGo
        collection_teddy = db[traveller]
        NEWLOCATION.pop('_id', None)
        collection_teddy.insert_one(NEWLOCATION)

        # Update journey summary
        ft_functions.summarize_journey(OURTRAVELLER)

        print('Done')
        return True
    except Exception as e:
        print('submit_new_location() exception: {}'.format(e))
        #send_email('Logger', 'gmaps_geocoder() exception: {}'.format(e))
        return False


def main_handler(users_input, chat_id, from_user, is_btn_click=False, geodata=None, media=False, other_input=False):
    '''
        Main handler. Function gets input from user (typed text OR payload data from button clicks), 'feeds' it
        to Dialogflow for NLP, receives intent and speech, and then depending on intent and context responds to user.
        users_input - typed text or callback_data from button, 'dummy' text in case location/photo/other content_types input
        chat_id - user's ID
        from_user - user's 1st name
        is_btn_click - whether it's callback_data from button (True) or manual text input (False, default)
        geodata - dictionary with latitude/longitude or None (default)
        media - if it's a photo (by default = False)
        other_input - any other content type besides text, button click, location or photo (by default = False)
    '''
    global CONTEXTS
    global NEWLOCATION

    print('\nCONTEXTS: {}\n'.format(CONTEXTS))

    if geodata:
        # message2 = 'Nice place ;)'
        # message3 = 'That\'s interesting ;)'
        # message4 = 'Hm..'
        short_reaction_variants = [';)', L10N['message2'][USER_LANGUAGE], L10N['message3'][USER_LANGUAGE], L10N['message4'][USER_LANGUAGE]]
        speech = random.choice(short_reaction_variants)
        intent = 'location_received'
    elif media:
        # message5 = 'Nice image ;)'
        short_reaction_variants = [';)', L10N['message5'][USER_LANGUAGE], L10N['message3'][USER_LANGUAGE], L10N['message4'][USER_LANGUAGE]]
        speech = random.choice(short_reaction_variants)
        intent = 'media_received'
    elif other_input:
        # message6 = 'Ok'
        # message7 = 'Okay'
        # messag8 = 'What would you like to do next?'
        short_reaction_variants = [';)', L10N['message6'][USER_LANGUAGE], L10N['message7'][USER_LANGUAGE], L10N['message4'][USER_LANGUAGE]]
        reaction = random.choice(short_reaction_variants)
        speech = '{}\n{}'.format(reaction, L10N['message8'][USER_LANGUAGE])
        intent = 'other_content_types'
    else:
        # Text input and callback_data from button clicks is 'fed' to Dialogflow for NLP
        dialoflows_response = dialogflow(users_input, chat_id, USER_LANGUAGE)
        speech = dialoflows_response['speech']
        intent = dialoflows_response['intent']

    # Block 0. User clicked/typed "Contact support" and the next text input should be sent to support email
    if 'contact_support' in CONTEXTS:
        # Text input is supposed or button clicks, other content types will be rejected
        if not is_btn_click:
            if not media \
                and not geodata \
                and not other_input:
                # Remove 'contact_support' from contexts
                CONTEXTS.remove('contact_support')
                # Redirect user's message to SUPPORT_EMAIL
                if send_email(chat_id, users_input):
                    # Report about successfull operation to user
                    # message9 = 'Your message was successfully sent to my author\n(<b>iurii.dziuban@gmail.com</b>).\nWhat would you like to do next?'
                    message = L10N['message9'][USER_LANGUAGE]
                    send_button_template_message(chat_id, text=message, buttons=[
                        {
                            # message84 = "Tell your story"
                            "title": L10N['message84'][USER_LANGUAGE],
                            "payload": L10N['message84'][USER_LANGUAGE]
                        },
                        {
                            # message45 = "FAQ"
                            "title": L10N['message45'][USER_LANGUAGE],
                            "payload": L10N['message45'][USER_LANGUAGE]
                        },
                        {
                            # message46 = "You got"
                            "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                            # message85 = "You got fellowtraveler"
                            "payload": L10N['message85'][USER_LANGUAGE]
                        }
                    ])

                else:
                    # Report about unsuccessfull operation to user
                    # message10 = 'Some problems occured when trying to send your message to my author (<b>iurii.dziuban@gmail.com</b>). Could you please write to his email yourself? Sorry for that..'
                    message = L10N['message10'][USER_LANGUAGE]
                    send_button_template_message(chat_id, text=message, buttons=[
                        {
                            # message84 = "Tell your story"
                            "title": L10N['message84'][USER_LANGUAGE],
                            "payload": L10N['message84'][USER_LANGUAGE]
                        },
                        {
                            # message45 = "FAQ"
                            "title": L10N['message45'][USER_LANGUAGE],
                            "payload": L10N['message45'][USER_LANGUAGE]
                        },
                        {
                            # message46 = "You got"
                            "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                            # message85 = "You got fellowtraveler"
                            "payload": L10N['message85'][USER_LANGUAGE]
                        }
                    ])
            else:
                # message11 = 'Sorry but I can send only text. Please type something ;)'
                message = L10N['message11'][USER_LANGUAGE]
                send_button_template_message(chat_id, text=message, buttons=[
                    {
                        # message50 = "Cancel"
                        "title": L10N['message50'][USER_LANGUAGE],
                        "payload": L10N['message50'][USER_LANGUAGE]
                    },
                    {
                        # message45 = "FAQ"
                        "title": L10N['message45'][USER_LANGUAGE],
                        "payload": L10N['message45'][USER_LANGUAGE]
                    },
                    {
                        # message51 = "Contact support"
                        "title": L10N['message51'][USER_LANGUAGE],
                        "payload": L10N['message51'][USER_LANGUAGE]
                    }
                ])
        else:
            # Button clicks
            # If user cancels sending message to support
            if intent == 'smalltalk.confirmation.cancel':
                CONTEXTS.remove('contact_support')
                # message12 = 'Cancelled\nWhat would you like to do next?'
                message = L10N['message12'][USER_LANGUAGE]
                send_button_template_message(chat_id, text=message, buttons=[
                    {
                        # message84 = "Tell your story"
                        "title": L10N['message84'][USER_LANGUAGE],
                        "payload": L10N['message84'][USER_LANGUAGE]
                    },
                    {
                        # message45 = "FAQ"
                        "title": L10N['message45'][USER_LANGUAGE],
                        "payload": L10N['message45'][USER_LANGUAGE]
                    },
                    {
                        # message46 = "You got"
                        "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                        # message85 = "You got fellowtraveler"
                        "payload": L10N['message85'][USER_LANGUAGE]
                    }
                ])
            # All other button clicks
            else:
                # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
                if not always_triggered(chat_id, intent, speech):
                    # All other text inputs/button clicks
                    default_fallback(chat_id, intent, speech)
                    #1982

    # Block 1. Traveler's story
    # Block 1-1. Reply to typing/clicking_buttons 'Yes'/'No' displayed after the intro block asking
    # if user want's to know more about T. journey
    # On exit of block if user enters 'Yes' - context 'journey_next_info', if 'No' or he/she clicks buttons of
    # previous blocks - contexts[] is cleared
    elif 'if_journey_info_needed' in CONTEXTS:
        if intent == 'smalltalk.confirmation.no':
            time.sleep(SHORT_TIMEOUT)
            if 'if_journey_info_needed' in CONTEXTS:
                CONTEXTS.remove('if_journey_info_needed')
            # message13 = 'Ok. Than we can just talk ;)\nJust in case here\'s my menu'
            message = L10N['message13'][USER_LANGUAGE]
            send_button_template_message(chat_id, text=message, buttons=[
                {
                    # message84 = "Tell your story"
                    "title": L10N['message84'][USER_LANGUAGE],
                    "payload": L10N['message84'][USER_LANGUAGE]
                },
                {
                    # message45 = "FAQ"
                    "title": L10N['message45'][USER_LANGUAGE],
                    "payload": L10N['message45'][USER_LANGUAGE]
                },
                {
                    # message46 = "You got"
                    "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                    # message85 = "You got fellowtraveler"
                    "payload": L10N['message85'][USER_LANGUAGE]
                }
            ])
        elif intent == 'smalltalk.confirmation.yes':
            journey_intro(chat_id, OURTRAVELLER)
            if 'if_journey_info_needed' in CONTEXTS:
                CONTEXTS.remove('if_journey_info_needed')
            CONTEXTS.append('journey_next_info')
        # If user is clicking buttons under previous blocks (for eg., buttons 'FAQ', <Traveler>'s story, You got traveler)
        # call classifier() with cleaned contexts
        else:
            # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
            if not always_triggered(chat_id, intent, speech):
                # All other text inputs/button clicks
                default_fallback(chat_id, intent, speech)

    # Block 1-2. Reply to entering/clicking buttons 'Next/Help' after block#1 showing overall map of traveler's journey;
    # on entry - context 'journey_next_info',
    # on exit of block if user clicks/types
    # 1) 'Next' and
    # a) if only 1 place was visited - contexts[] is cleared
    # b) if several places were visited - 2 contexts are added:
    # 'journey_summary_presented' and {'location_shown': None, 'total_locations': total_locations}
    # 2) 'Help' or clicks buttons of previous blocks - contexts[] is cleared
    elif 'journey_next_info' in CONTEXTS:
        if intent == 'next_info':
            total_locations = journey_begins(chat_id, OURTRAVELLER)
            time.sleep(SHORT_TIMEOUT)
            if total_locations == 0:
                # message14 = 'My journey hasn\'nt started yet. Will you add my first location?'
                message = L10N['message14'][USER_LANGUAGE]
                send_button_template_message(chat_id, text=message, buttons=[
                    {
                        # message84 = "Tell your story"
                        "title": L10N['message84'][USER_LANGUAGE],
                        "payload": L10N['message84'][USER_LANGUAGE]
                    },
                    {
                        # message45 = "FAQ"
                        "title": L10N['message45'][USER_LANGUAGE],
                        "payload": L10N['message45'][USER_LANGUAGE]
                    },
                    {
                        # message46 = "You got"
                        "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                        # message85 = "You got fellowtraveler"
                        "payload": L10N['message85'][USER_LANGUAGE]
                    }
                ])

            # If there's only 1 location, show it and present basic menu ("Teddy's story/Help/You got Teddy?")
            elif total_locations == 1:
                the_1st_place(chat_id, OURTRAVELLER, False)
                # message15 = 'And that\'s all my journey so far ;)\n\nWhat would you like to do next? We can just talk or use this menu:'
                message = L10N['message15'][USER_LANGUAGE]
                send_button_template_message(chat_id, text=message, buttons=[
                    {
                        # message84 = "Tell your story"
                        "title": L10N['message84'][USER_LANGUAGE],
                        "payload": L10N['message84'][USER_LANGUAGE]
                    },
                    {
                        # message45 = "FAQ"
                        "title": L10N['message45'][USER_LANGUAGE],
                        "payload": L10N['message45'][USER_LANGUAGE]
                    },
                    {
                        # message46 = "You got"
                        "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                        # message85 = "You got fellowtraveler"
                        "payload": L10N['message85'][USER_LANGUAGE]
                    }
                ])
                if 'journey_next_info' in CONTEXTS:
                    CONTEXTS.remove('journey_next_info')
            # If there are >1 visited places, ask user if he wants to see them ("Yes/No/Help")
            else:
                # message16 = 'Would you like to see all places that I have been to?'
                message = L10N['message16'][USER_LANGUAGE]
                send_button_template_message(chat_id, text=message, buttons=[
                    {
                        # message47 = "Yes"
                        'title': L10N['message47'][USER_LANGUAGE],
                        'payload': L10N['message47'][USER_LANGUAGE]
                    },
                    {
                        # message48 = "No, thanks"
                        'title': L10N['message48'][USER_LANGUAGE],
                        'payload': L10N['message48'][USER_LANGUAGE]
                    }
                ])
                if 'journey_next_info' in CONTEXTS:
                    CONTEXTS.remove('journey_next_info')
                CONTEXTS.append('journey_summary_presented')
                CONTEXTS.append({'location_shown': None, 'total_locations': total_locations})
        elif intent == 'show_faq':
            if 'journey_next_info' in CONTEXTS:
                CONTEXTS.remove('journey_next_info')
            get_help(chat_id)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            # Buttons | You got Teddy? | Teddy's story are activated irrespective of context
            if not always_triggered(chat_id, intent, speech):
                # All other text inputs/button clicks
                default_fallback(chat_id, intent, speech)

    # Block 1-3. Reply to entering/clicking buttons 'Yes/No,thanks/Help' displayed after the prevoius block with journey summary;
    # on entry - 2 contexts 'journey_summary_presented' and {'location_shown': None, 'total_locations': total_locations},
    # on exit:
    # 1) if user types/clicks 'Yes' - 2 contexts 'locations_iteration' and {'location_shown': 0, 'total_locations': total_locations}
    # 2) if user types/clicks 'No/Help' or clicks buttons of previous blocks - contexts[] is cleared
    elif 'journey_summary_presented' in CONTEXTS:
        if intent == 'smalltalk.confirmation.yes':  # "Yes" button is available if >1 places were visited
            the_1st_place(chat_id, OURTRAVELLER, True)
            if 'journey_summary_presented' in CONTEXTS:
                CONTEXTS.remove('journey_summary_presented')
            if 'locations_iteration' not in CONTEXTS:
                CONTEXTS.append('locations_iteration')
            for context in CONTEXTS:
                if 'location_shown' in context:
                    context['location_shown'] = 0
        elif intent == 'smalltalk.confirmation.no':
            time.sleep(SHORT_TIMEOUT)
            if 'journey_summary_presented' in CONTEXTS:
                CONTEXTS.remove('journey_summary_presented')
            # message13 = 'Ok. Than we can just talk ;)\nJust in case here\'s my menu'
            message = L10N['message13'][USER_LANGUAGE]
            send_button_template_message(chat_id, text=message, buttons=[
                {
                    # message84 = "Tell your story"
                    "title": L10N['message84'][USER_LANGUAGE],
                    "payload": L10N['message84'][USER_LANGUAGE]
                },
                {
                    # message45 = "FAQ"
                    "title": L10N['message45'][USER_LANGUAGE],
                    "payload": L10N['message45'][USER_LANGUAGE]
                },
                {
                    # message46 = "You got"
                    "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                    # message85 = "You got fellowtraveler"
                    "payload": L10N['message85'][USER_LANGUAGE]
                }
            ])

        elif intent == 'show_faq':
            if 'journey_summary_presented' in CONTEXTS:
                CONTEXTS.remove('journey_summary_presented')
            get_help(chat_id)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            # Buttons | You got Teddy? | Teddy's story are activated irrespective of context
            if not always_triggered(chat_id, intent, speech):
                # All other text inputs/button clicks
                default_fallback(chat_id, intent, speech)

    # Block 1-4. Reply to entering/clicking buttons 'Next/Help' after block#3 showing the 1st place among several visited;
    # is executed in cycle
    # on entry - 2 contexts: 'locations_iteration' and {'location_shown': X, 'total_locations': Y}
    # (where X = the serial number of place visited, for eg. 0 - the 1st place, 2 - the 3rd place),
    # on exit:
    # 1) if user types/clicks 'Yes' and
    # a) if the last place visited is shown - contexts[] is cleared
    # b) if places to show remain - 2 contexts: 'locations_iteration' and {'location_shown': X+1, 'total_locations': Y}
    # 2) types/ckicks button 'Help' or buttons of previous blocks - contexts[] is cleared
    elif 'locations_iteration' in CONTEXTS:
        if intent == 'next_info':
            location_shown = 0
            total_locations = 1
            for context in CONTEXTS:
                if 'location_shown' in context:
                    location_shown = context['location_shown']
                    total_locations = context['total_locations']
            if total_locations - (location_shown + 1) == 1:
                if 'locations_iteration' in CONTEXTS:
                    CONTEXTS.remove('locations_iteration')
                every_place(chat_id, OURTRAVELLER, location_shown + 1, False)
                # message15 = 'And that\'s all my journey so far ;)\n\nWhat would you like to do next? We can just talk or use this menu:'
                send_button_template_message(chat_id, text=L10N['message15'][USER_LANGUAGE], buttons=[
                    {
                        # message84 = "Tell your story"
                        "title": L10N['message84'][USER_LANGUAGE],
                        "payload": L10N['message84'][USER_LANGUAGE]
                    },
                    {
                        # message45 = "FAQ"
                        "title": L10N['message45'][USER_LANGUAGE],
                        "payload": L10N['message45'][USER_LANGUAGE]
                    },
                    {
                        # message46 = "You got"
                        "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                        # message85 = "You got fellowtraveler"
                        "payload": L10N['message85'][USER_LANGUAGE]
                    }
                ])
            elif total_locations - (location_shown + 1) > 1:
                every_place(chat_id, OURTRAVELLER, location_shown + 1, True)
                for context in CONTEXTS:
                    if 'location_shown' in context:
                        context['location_shown'] += 1
        elif intent == 'show_faq':
            if 'locations_iteration' in CONTEXTS:
                CONTEXTS.remove('locations_iteration')
            get_help(chat_id)
        # If user is clicking buttons under previous blocks - call classifier() with cleaned contexts
        else:
            # Buttons | You got Teddy? | Teddy's story are activated irrespective of context
            if not always_triggered(chat_id, intent, speech):
                # All other text inputs/button clicks
                default_fallback(chat_id, intent, speech)

    # Block 2. If you got a fellow traveler
    # Block 2-1. User clicked button/typed 'You got Teddy?' and was prompted to enter the secret code
    elif 'enters_code' in CONTEXTS:
        # If user enters 'Cancel' or smth similar after entering invalid secret_code - update contexts
        if intent == 'smalltalk.confirmation.cancel':
            if 'enters_code' in CONTEXTS:
                CONTEXTS.remove('enters_code')
            # message6, message8 = 'Ok. What would you like to do next?'
            message = '{}. {}'.format(L10N['message6'][USER_LANGUAGE], L10N['message8'][USER_LANGUAGE])
            send_button_template_message(chat_id, text=message, buttons=[
                {
                    # message84 = "Tell your story"
                    "title": L10N['message84'][USER_LANGUAGE],
                    "payload": L10N['message84'][USER_LANGUAGE]
                },
                {
                    # message45 = "FAQ"
                    "title": L10N['message45'][USER_LANGUAGE],
                    "payload": L10N['message45'][USER_LANGUAGE]
                },
                {
                    # message46 = "You got"
                    "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                    # message85 = "You got fellowtraveler"
                    "payload": L10N['message85'][USER_LANGUAGE]
                }
            ])
        elif intent == 'contact_support':
            if 'enters_code' in CONTEXTS:
                CONTEXTS.remove('enters_code')
            CONTEXTS.append('contact_support')
            # message17 = 'Any problems, questions, suggestions, remarks, proposals etc? Please enter them below or write to my author\'s email <b>iurii.dziuban@gmail.com</b>\n\n You may also consider visiting <a href="https://iuriid.github.io">iuriid.github.io</a>.'
            message = L10N['message17'][USER_LANGUAGE]
            send_button_template_message(chat_id, text=message,  buttons=[
                                              {
                                                  # message50 = "Cancel"
                                                  "title": L10N['message50'][USER_LANGUAGE],
                                                  "payload": L10N['message50'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message45 = "FAQ"
                                                  "title": L10N['message45'][USER_LANGUAGE],
                                                  "payload": L10N['message45'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message51 = "Contact support"
                                                  "title": L10N['message51'][USER_LANGUAGE],
                                                  "payload": L10N['message51'][USER_LANGUAGE]
                                              }
                                          ])

        # If user enters whatever else, not == intent 'smalltalk.confirmation.cancel'
        else:
            if not is_btn_click:
                secret_code_entered = users_input
                if secret_code_validation(secret_code_entered):
                    if 'enters_code' in CONTEXTS:
                        CONTEXTS.remove('enters_code')
                    CONTEXTS.append('code_correct')
                    # message18 = 'Code correct, thanks! Sorry for formalities'
                    send_text_message(chat_id, L10N['message18'][USER_LANGUAGE])

                    ''' message19 =  As I might have said, my goal is to see the world.'
                                     '\n\n And as your fellow traveler I will kindly ask you for 2 things:'
                                     '\n- Please show me some nice places of your city/country or please take me with you if you are traveling somewhere. '
                                     'Please document where I have been using the button "<b>Add location</b>".'
                                     '\n - After some time please pass me to somebody else ;)'
                                     '\n\n For more detailed instructions - please click "<b>Instructions</b>"'
                                     '\n\nIf you\'ve got some problems, you can also write to my author (button "<b>Contact support</b>")
                    '''
                    send_button_template_message(chat_id, text=L10N['message19'][USER_LANGUAGE], buttons=[
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        },
                        {
                            # message53 = "Add location"
                            "title": L10N['message53'][USER_LANGUAGE],
                            "payload": L10N['message53'][USER_LANGUAGE]
                        },
                        {
                            # message51 = "Contact support"
                            "title": L10N['message51'][USER_LANGUAGE],
                            "payload": L10N['message51'][USER_LANGUAGE]
                        }
                    ])

                else:
                    # message20 = 'Incorrect secret code. Please try again'
                    send_button_template_message(chat_id, text=L10N['message20'][USER_LANGUAGE], buttons=[
                        {
                            # message50 = "Cancel"
                            "title": L10N['message50'][USER_LANGUAGE],
                            "payload": L10N['message50'][USER_LANGUAGE]
                        },
                        {
                            # message45 = "FAQ"
                            "title": L10N['message45'][USER_LANGUAGE],
                            "payload": L10N['message45'][USER_LANGUAGE]
                        },
                        {
                            # message51 = "Contact support"
                            "title": L10N['message51'][USER_LANGUAGE],
                            "payload": L10N['message51'][USER_LANGUAGE]
                        }
                    ])

            else:
                # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
                if not always_triggered(chat_id, intent, speech):
                    # All other text inputs/button clicks
                    default_fallback(chat_id, intent, speech)

    # Block 2-2. User entered correct password and now can get 'priviledged' instructions, add location or contact support
    # Context 'code_correct' is being cleared after adding a new location, clicking 'Contact support' or if user enters
    # commands outside of of block that is displayed after entering secret code
    elif 'code_correct' in CONTEXTS:
        if intent == 'contact_support':
            CONTEXTS.clear()
            CONTEXTS.append('code_correct')
            CONTEXTS.append('contact_support')
            # message17 = 'Any problems, questions, suggestions, remarks, proposals etc? Please enter them below or write to my author\'s email <b>iurii.dziuban@gmail.com</b>\n\n You may also consider visiting <a href="https://iuriid.github.io">iuriid.github.io</a>.'
            message = L10N['message17'][USER_LANGUAGE]
            send_button_template_message(chat_id, text=message,  buttons=[
                                              {
                                                  # message50 = "Cancel"
                                                  "title": L10N['message50'][USER_LANGUAGE],
                                                  "payload": L10N['message50'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message45 = "FAQ"
                                                  "title": L10N['message45'][USER_LANGUAGE],
                                                  "payload": L10N['message45'][USER_LANGUAGE]
                                              },
                                              {
                                                  # message51 = "Contact support"
                                                  "title": L10N['message51'][USER_LANGUAGE],
                                                  "payload": L10N['message51'][USER_LANGUAGE]
                                              }
                                          ])
        elif intent == 'show_instructions':
            CONTEXTS.clear()
            CONTEXTS.append('code_correct')
            # message21 = 'Here are our detailed instructions for those who got'
            send_button_template_message(chat_id, text=L10N['message21'][USER_LANGUAGE], buttons=[
                {
                    # message52 = "Instructions"
                    "title": L10N['message52'][USER_LANGUAGE],
                    "payload": L10N['message52'][USER_LANGUAGE]
                },
                {
                    # message53 = "Add location"
                    "title": L10N['message53'][USER_LANGUAGE],
                    "payload": L10N['message53'][USER_LANGUAGE]
                },
                {
                    # message51 = "Contact support"
                    "title": L10N['message51'][USER_LANGUAGE],
                    "payload": L10N['message51'][USER_LANGUAGE]
                }
            ])

        elif intent == 'add_location':
            # message22 = 'First please tell <i>where</i>'
            # message23 = '<i>is now</i> (you may use the button \"<b>Share your location</b>\" below) \n\nor \n\n<i>where he was</i> photographed (to enter address which differs from your current location please <b>attach >> Location</b> and drag the map to desired place)'
            message = '{} {} {}'.format(L10N['message22'][USER_LANGUAGE], OURTRAVELLER, L10N['message23'][USER_LANGUAGE])
            send_text_message_share_location(chat_id, message)

            if 'location_input' not in CONTEXTS:
                CONTEXTS.append('location_input')
        else:
            # Block 2-3. User enters location ('location_input' in contexts)
            # It can be either his/her current location shared using Telegram's location sharing function or a plain text input
            # from text_handler() which should be processed using Google Maps Geocoding API
            if 'location_input' in CONTEXTS:
                # And user shared his/her location
                if intent == 'location_received':  # sharing or current location
                    # Reverse geocode lat/lng to geodata
                    # Also as this is the 1st data for new locations, fill the fields 'author', 'channel' and 'user_id_on_channel'
                    NEWLOCATION['author'] = from_user
                    NEWLOCATION['user_id_on_channel'] = chat_id
                    NEWLOCATION['channel'] = 'Facebook'
                    NEWLOCATION['longitude'] = geodata['lng']
                    NEWLOCATION['latitude'] = geodata['lat']
                    # Erase the remaining fields of NEWLOCATION in case user restarts
                    NEWLOCATION['formatted_address'] = None
                    NEWLOCATION['locality'] = None
                    NEWLOCATION['administrative_area_level_1'] = None
                    NEWLOCATION['country'] = None
                    NEWLOCATION['place_id'] = None
                    NEWLOCATION['comment'] = None
                    NEWLOCATION['photos'] = []
                    NEWLOCATION['photos_FB_ids'] = []
                    NEWLOCATION['photos_TG_ids'] = []

                    gmaps_geocoder(geodata['lat'], geodata['lng'])
                    CONTEXTS.remove('location_input')
                    # Ready for the next step - adding photos
                    CONTEXTS.append('media_input')
                    # message24 = 'Thanks! Now could you please upload some photos with'
                    # message25 = 'from this place?\nSelfies with'
                    # message26 = 'are also welcome ;)'
                    message = '{0} {1} {2} {1} {3}'.format(L10N['message24'][USER_LANGUAGE], OURTRAVELLER, L10N['message25'][USER_LANGUAGE], L10N['message26'][USER_LANGUAGE])
                    send_button_template_message(chat_id, text=message, buttons=[
                        {
                            # message49 = "Next"
                            "title": L10N['message49'][USER_LANGUAGE],
                            "payload": L10N['message49'][USER_LANGUAGE]
                        },
                        {
                            # message55 = "Reset"
                            "title": L10N['message55'][USER_LANGUAGE],
                            "payload": L10N['message55'][USER_LANGUAGE]
                        },
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        }
                    ])

                # User cancels location entry - leave 'code_correct' context, remove 'location_input'
                elif intent == 'smalltalk.confirmation.cancel':
                    CONTEXTS.remove('location_input')

                    # message6, message8 = 'Ok. What would you like to do next?'
                    message = '{}. {}'.format(L10N['message6'][USER_LANGUAGE], L10N['message8'][USER_LANGUAGE])
                    send_button_template_message(chat_id, text=message, buttons=[
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        },
                        {
                            # message53 = "Add location"
                            "title": L10N['message53'][USER_LANGUAGE],
                            "payload": L10N['message53'][USER_LANGUAGE]
                        },
                        {
                            # message51 = "Contact support"
                            "title": L10N['message51'][USER_LANGUAGE],
                            "payload": L10N['message51'][USER_LANGUAGE]
                        }
                    ])

                # User wants detailed instructions - contexts unchanged
                elif intent == 'show_instructions':
                    # message21 = 'Here are the detailed instructions for those who got'
                    message = '{} {}'.format(L10N['message6'][USER_LANGUAGE], OURTRAVELLER)
                    send_button_template_message(chat_id, text=message, buttons=[
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        },
                        {
                            # message53 = "Add location"
                            "title": L10N['message53'][USER_LANGUAGE],
                            "payload": L10N['message53'][USER_LANGUAGE]
                        },
                        {
                            # message51 = "Contact support"
                            "title": L10N['message51'][USER_LANGUAGE],
                            "payload": L10N['message51'][USER_LANGUAGE]
                        }
                    ])

                # User should be entering location but he/she types smth or clicks other buttons besides 'Cancel' or
                # 'Instructions'
                else:
                    # message27 = 'That doesn\'t look like a valid location. Please try once again'
                    send_button_template_message(chat_id, text=L10N['message27'][USER_LANGUAGE], buttons=[
                        {
                            # message50 = "Cancel"
                            "title": L10N['message50'][USER_LANGUAGE],
                            "payload": L10N['message50'][USER_LANGUAGE]
                        },
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        }
                    ])

            # Block 2-4. User should be uploading a/some photo/-s.
            elif 'media_input' in CONTEXTS:
                # User did upload some photos - thank him/her and ask for a comment
                if intent == 'media_received':
                    # If user uploaded several images - respond only to the 1st one
                    if 'last_media_input' not in CONTEXTS:
                        if 'any_comments' not in CONTEXTS:
                            CONTEXTS.append('any_comments')
                        # message28 = 'Thank you!'
                        # message29 = 'Any comments (how did you get'
                        # message30 = ', what did you feel, any messages for future'
                        # message31 = '\'s fellow travelers)?'
                        message = '{0}\n{1} {2}{3} {2}{4}'.format(L10N['message28'][USER_LANGUAGE], L10N['message29'][USER_LANGUAGE], OURTRAVELLER, L10N['message30'][USER_LANGUAGE], L10N['message31'][USER_LANGUAGE])
                        send_button_template_message(chat_id, text=message, buttons=[
                            {
                                # message49 = "Next"
                                "title": L10N['message49'][USER_LANGUAGE],
                                "payload": L10N['message49'][USER_LANGUAGE]
                            },
                            {
                                # message55 = "Reset"
                                "title": L10N['message55'][USER_LANGUAGE],
                                "payload": L10N['message55'][USER_LANGUAGE]
                            },
                            {
                                # message52 = "Instructions"
                                "title": L10N['message52'][USER_LANGUAGE],
                                "payload": L10N['message52'][USER_LANGUAGE]
                            }
                        ])

                # User refused to upload photos, clicked 'Next' - ask him/her for a comment
                elif intent == 'next_info':
                    CONTEXTS.clear()
                    CONTEXTS.append('code_correct')
                    CONTEXTS.append('any_comments')
                    # message6 = 'Ok'
                    # message29 = 'Any comments (how did you get'
                    # message30 = ', what did you feel, any messages for future'
                    # message31 = '\'s fellow travelers)?'
                    message = '{0}\n{1} {2}{3} {2}{4}'.format(
                                         L10N['message6'][USER_LANGUAGE],  L10N['message29'][USER_LANGUAGE], OURTRAVELLER, L10N['message30'][USER_LANGUAGE], L10N['message31'][USER_LANGUAGE])
                    send_button_template_message(chat_id, text=message, buttons=[
                        {
                            # message49 = "Next"
                            "title": L10N['message49'][USER_LANGUAGE],
                            "payload": L10N['message49'][USER_LANGUAGE]
                        },
                        {
                            # message55 = "Reset"
                            "title": L10N['message55'][USER_LANGUAGE],
                            "payload": L10N['message55'][USER_LANGUAGE]
                        },
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        }
                    ])

                # User resets location entry
                elif intent == 'reset':
                    CONTEXTS.clear()
                    CONTEXTS.append('code_correct')
                    # message32 = 'Ok, let\'s try once again'
                    send_button_template_message(chat_id, text=L10N['message32'][USER_LANGUAGE], buttons=[
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        },
                        {
                            # message53 = "Add location"
                            "title": L10N['message53'][USER_LANGUAGE],
                            "payload": L10N['message53'][USER_LANGUAGE]
                        },
                        {
                            # message51 = "Contact support"
                            "title": L10N['message51'][USER_LANGUAGE],
                            "payload": L10N['message51'][USER_LANGUAGE]
                        }
                    ])

                else:
                    # User should be uploading photos but he/she didn't and also didn't click 'Cancel' but
                    # enters/clicks something else
                    # Buttons | You got Teddy? | Teddy's story | Help | etc are activated irrespective of context
                    if not always_triggered(chat_id, intent, speech):
                        # All other text inputs/button clicks
                        default_fallback(chat_id, intent, speech)

            # Block 2-5. User was prompted to leave a comment
            # He/she might enter text (Ok), click buttons under the prev. block (Next/Reset/Instructions) or enter
            # other input types (for eg., a sticker, photo, location etc) (not Ok)
            elif 'any_comments' in CONTEXTS \
                    and 'last_media_input' not in CONTEXTS: # that is last input was not a photo, photo/-s input in prev. block finished
                # Button clicks
                if is_btn_click:
                    # User doesn't want to give a comment
                    if intent == 'next_info':
                        NEWLOCATION['comment'] = ''
                        CONTEXTS.remove('any_comments')
                        CONTEXTS.append('ready_for_submit')
                        # Resume up user's input (location, photos, comment) and ask to confirm or reset
                        time.sleep(SHORT_TIMEOUT)
                        # message33 = 'In total your input will look like this:'
                        send_text_message(chat_id, L10N['message33'][USER_LANGUAGE])

                        if new_location_summary(chat_id, from_user):
                            # message34 = 'Is that Ok? If yes, please click \"<b>Submit</b>\".\nOtherwise click \"<b>Reset</b>\" to start afresh'
                            send_button_template_message(chat_id, text=L10N['message34'][USER_LANGUAGE], buttons=[
                                {
                                    # message56 = "Submit"
                                    "title": L10N['message56'][USER_LANGUAGE],
                                    "payload": L10N['message56'][USER_LANGUAGE]
                                },
                                {
                                    # message55 = "Reset"
                                    "title": L10N['message55'][USER_LANGUAGE],
                                    "payload": L10N['message55'][USER_LANGUAGE]
                                }
                            ])

                        else:
                            # message35 = 'Hmm.. Some error occured. Could you please try again?'
                            send_button_template_message(chat_id, text=L10N['message35'][USER_LANGUAGE], buttons=[
                                {
                                    # message52 = "Instructions"
                                    "title": L10N['message52'][USER_LANGUAGE],
                                    "payload": L10N['message52'][USER_LANGUAGE]
                                },
                                {
                                    # message53 = "Add location"
                                    "title": L10N['message53'][USER_LANGUAGE],
                                    "payload": L10N['message53'][USER_LANGUAGE]
                                },
                                {
                                    # message51 = "Contact support"
                                    "title": L10N['message51'][USER_LANGUAGE],
                                    "payload": L10N['message51'][USER_LANGUAGE]
                                }
                            ])

                    elif intent == 'reset':
                        CONTEXTS.clear()
                        CONTEXTS.append('code_correct')
                        # message36 = 'Ok, let\'s try once again'
                        send_button_template_message(chat_id, text=L10N['message36'][USER_LANGUAGE], buttons=[
                            {
                                # message52 = "Instructions"
                                "title": L10N['message52'][USER_LANGUAGE],
                                "payload": L10N['message52'][USER_LANGUAGE]
                            },
                            {
                                # message53 = "Add location"
                                "title": L10N['message53'][USER_LANGUAGE],
                                "payload": L10N['message53'][USER_LANGUAGE]
                            },
                            {
                                # message51 = "Contact support"
                                "title": L10N['message51'][USER_LANGUAGE],
                                "payload": L10N['message51'][USER_LANGUAGE]
                            }
                        ])

                    else:
                        # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
                        if not always_triggered(chat_id, intent, speech):
                            # All other text inputs/button clicks
                            default_fallback(chat_id, intent, speech)
                # Impropriate input (stickers, photo, location etc)
                elif geodata or media or other_input:
                    # message37 = 'Sorry but only text is accepted as a comment. Could you please enter a text message?'
                    send_button_template_message(chat_id, text=L10N['message37'][USER_LANGUAGE], buttons=[
                        {
                            # message49 = "Next"
                            "title": L10N['message49'][USER_LANGUAGE],
                            "payload": L10N['message49'][USER_LANGUAGE]
                        },
                        {
                            # message55 = "Reset"
                            "title": L10N['message55'][USER_LANGUAGE],
                            "payload": L10N['message55'][USER_LANGUAGE]
                        },
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        }
                    ])

                # Text input
                else:
                    # Update contexts - leave only 'code_correct' and 'any_comments'
                    CONTEXTS.clear()
                    CONTEXTS.append('code_correct')
                    CONTEXTS.append('ready_for_submit')

                    # Show user what he/she has entered as a comment
                    # message38 = 'Ok. So we\'ll treat the following as your comment:'
                    message = '{}\n{}'.format(L10N['message38'][USER_LANGUAGE], users_input)
                    send_text_message(chat_id, message)

                    # Save user's comment to NEWLOCATION
                    NEWLOCATION['comment'] = users_input

                    # Resume up user's input (location, photos, comment) and ask to confirm or reset
                    time.sleep(LONG_TIMEOUT)
                    # message33 = 'In total your input will look like this:'
                    send_text_message(chat_id, L10N['message33'][USER_LANGUAGE])

                    if new_location_summary(chat_id, from_user):
                        time.sleep(SHORT_TIMEOUT)
                        # message34 = 'Is that Ok? If yes, please click \"<b>Submit</b>\".\nOtherwise click \"<b>Reset</b>\" to start afresh'
                        send_button_template_message(chat_id, text=L10N['message34'][USER_LANGUAGE], buttons=[
                            {
                                # message56 = "Submit"
                                "title": L10N['message56'][USER_LANGUAGE],
                                "payload": L10N['message56'][USER_LANGUAGE]
                            },
                            {
                                # message55 = "Reset"
                                "title": L10N['message55'][USER_LANGUAGE],
                                "payload": L10N['message55'][USER_LANGUAGE]
                            }
                        ])
                    else:
                        # message35 = 'Hmm.. Some error occured. Could you please try again?'
                        send_button_template_message(chat_id, text=L10N['message35'][USER_LANGUAGE], buttons=[
                            {
                                # message52 = "Instructions"
                                "title": L10N['message52'][USER_LANGUAGE],
                                "payload": L10N['message52'][USER_LANGUAGE]
                            },
                            {
                                # message53 = "Add location"
                                "title": L10N['message53'][USER_LANGUAGE],
                                "payload": L10N['message53'][USER_LANGUAGE]
                            },
                            {
                                # message51 = "Contact support"
                                "title": L10N['message51'][USER_LANGUAGE],
                                "payload": L10N['message51'][USER_LANGUAGE]
                            }
                        ])


            # Block 2-6. Submitting new location - user clicked 'Submit'
            elif 'ready_for_submit' in CONTEXTS:
                if intent == 'submit':
                    # Clear all contexts
                    CONTEXTS.clear()

                    # Save location and get the new secret code
                    location_submitted = submit_new_location(OURTRAVELLER)
                    new_code_generated = ft_functions.code_regenerate(OURTRAVELLER)

                    if location_submitted and new_code_generated:
                        # message40 = 'New location added!\n\nSecret code for adding the next location:
                        # message41 = 'Please save it somewhere or don\'t delete this message.\nIf you are going to pass'
                        # message42 = 'to somebody please write this code similar to how you received it'
                        message = '{0} {1}\n\n{2} {3} {4}'.format(
                                            L10N['message40'][USER_LANGUAGE], new_code_generated, L10N['message41'][USER_LANGUAGE], OURTRAVELLER, L10N['message42'][USER_LANGUAGE])
                        send_button_template_message(chat_id, text=message, buttons=[
                            {
                                # message84 = "Tell your story"
                                "title": L10N['message84'][USER_LANGUAGE],
                                "payload": L10N['message84'][USER_LANGUAGE]
                            },
                            {
                                # message45 = "FAQ"
                                "title": L10N['message45'][USER_LANGUAGE],
                                "payload": L10N['message45'][USER_LANGUAGE]
                            },
                            {
                                # message46 = "You got"
                                "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                                # message85 = "You got fellowtraveler"
                                "payload": L10N['message85'][USER_LANGUAGE]
                            }
                        ])
                    else:
                        # message43 = 'Hmm... Sorry, but for some reason I failed to save your data to database.\nI informed my author (<b>iurii.dziuban@gmail.com</b>) about this and hope that he finds the reason soon.\nSorry for inconveniences..'
                        send_button_template_message(chat_id, text=L10N['message43'][USER_LANGUAGE], buttons=[
                            {
                                # message84 = "Tell your story"
                                "title": L10N['message84'][USER_LANGUAGE],
                                "payload": L10N['message84'][USER_LANGUAGE]
                            },
                            {
                                # message45 = "FAQ"
                                "title": L10N['message45'][USER_LANGUAGE],
                                "payload": L10N['message45'][USER_LANGUAGE]
                            },
                            {
                                # message46 = "You got"
                                "title": "{} {}?".format(L10N['message46'][USER_LANGUAGE], OURTRAVELLER),
                                # message85 = "You got fellowtraveler"
                                "payload": L10N['message85'][USER_LANGUAGE]
                            }
                        ])
                elif intent == 'reset':
                    CONTEXTS.clear()
                    CONTEXTS.append('code_correct')
                    # message36 = 'Ok, let\'s try once again'
                    send_button_template_message(chat_id, text=L10N['message36'][USER_LANGUAGE], buttons=[
                        {
                            # message52 = "Instructions"
                            "title": L10N['message52'][USER_LANGUAGE],
                            "payload": L10N['message52'][USER_LANGUAGE]
                        },
                        {
                            # message53 = "Add location"
                            "title": L10N['message53'][USER_LANGUAGE],
                            "payload": L10N['message53'][USER_LANGUAGE]
                        },
                        {
                            # message51 = "Contact support"
                            "title": L10N['message51'][USER_LANGUAGE],
                            "payload": L10N['message51'][USER_LANGUAGE]
                        }
                    ])
                else:
                    # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
                    if not always_triggered(chat_id, intent, speech):
                        # All other text inputs/button clicks
                        default_fallback(chat_id, intent, speech)

            else:
                # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
                if not always_triggered(chat_id, intent, speech):
                    # All other text inputs/button clicks
                    default_fallback(chat_id, intent, speech)

    # General endpoint - if user typed/clicked something and contexts[] is empty
    else:
        # Buttons | You got Teddy? | Teddy's story | Help | are activated irrespective of context
        if not always_triggered(chat_id, intent, speech):
            # All other text inputs/button clicks
            default_fallback(chat_id, intent, speech)

    # Console logging
    print('')
    if is_btn_click:
        input_type = 'button click'
    elif media:
        input_type = 'media upload'
    elif geodata:
        input_type = 'location input'
    elif other_input:
        input_type = 'other content types'
    else:
        input_type = 'entered manually'
    #print('User\'s input: {} ({})'.format(users_input, input_type))
    #print('Intent: {}, speech: {}'.format(intent, speech))
    #print('Contexts: {}'.format(CONTEXTS))

############################################ Functions END #######################################

@babel.localeselector
def get_locale():
    user_language = request.cookies.get('UserPreferredLanguage')
    if user_language != None:
        return user_language
    else:
        return request.accept_languages.best_match(LANGUAGES.keys())


@app.route('/service/register/', methods=['GET', 'POST'])
@notloggedin_required
@csrf.exempt
def register():
    next_redirect = '/'
    try:
        registrationform = RegistrationForm()

        # Check which traveler user was watching
        which_traveler = ft_functions.get_traveler()
        if which_traveler != 'All':
            next_redirect = '/{}/'.format(which_traveler)

        # Registration data have been submitted (POST)
        if request.method == 'POST':
            if registrationform.validate_on_submit():
                email = registrationform.email.data
                password = sha256_crypt.encrypt(str(registrationform.password.data))

                client = MongoClient()
                db = client.TeddyGo
                users = db.users

                # Check if user with such email exists
                email_already_submitted = users.find_one({"email": email})
                if email_already_submitted:
                    if email_already_submitted['email_verified']:
                        flash(lazy_gettext("User with email {} is already registered. Please choose a different email address or <a href='../login/'>log in</a>").format(email), 'header')
                        return redirect(url_for('register'))
                    else:
                        flash(lazy_gettext(
                            "User with email {} is already registered but email has not been verified yet").format(email), 'header')
                        return redirect(url_for('register'))

                # If a new user
                else:
                    userid = str(uuid.uuid4())
                    email_verification_link = '{}/verify_user/{}/{}'.format(SITE_URL, email, userid)

                    users.insert_one(
                        {
                            'email': email,
                            'password': password,
                            'email_verified': False,
                            "email_verification_code": sha256_crypt.encrypt(userid),
                            'which_traveler': which_traveler
                        }
                    )

                    # Send user a confirmation email
                    topic = gettext("Fellowtraveler.club: email verification link")
                    recipients = [email]
                    message = gettext("Hi! Thanks for registering on <b><a href='https://fellowtraveler.club'>fellowtraveler.club</a></b>.<br><br>" \
                               "Please verify your email address by clicking on the following link:<br><b><a href='{0}' target='_blank'>{0}</a></b><br><br>" \
                               "If it wasn't you please simply ignore this message").format(email_verification_link)
                    send_mail(topic=topic, recipients=recipients, message=message)

                    flash(lazy_gettext('Almost finished. To complete registration please click on the verification link that has been sent to your email'), 'header')

                    return redirect(next_redirect)
            else:
                print('Registration form input did not validate')
                return render_template('register.html', registrationform=registrationform)
        # GET request for a registration form
        else:
            return render_template('register.html', registrationform=registrationform)
    except Exception as e:
        print('register() exception: {}'.format(e))
        return redirect(next_redirect)


@app.route('/service/login/', methods=['GET', 'POST'])
@notloggedin_required
@csrf.exempt
def login():
    try:
        loginform = LoginForm()

        # Check which traveler user was watching
        which_traveler = ft_functions.get_traveler()

        # Login data have been submitted (POST)
        if request.method == 'POST':
            print('Login() POST')
            if loginform.validate_on_submit():
                print('Login form validates')
                email = loginform.email.data
                password = loginform.password.data

                client = MongoClient()
                db = client.TeddyGo
                users = db.users

                # Check if email exist in DB and is verified, exit if not
                docID = None
                if users.find_one({'email': email}):
                    docID = users.find_one({'email': email}).get('_id')
                    status = users.find_one({'_id': docID}).get('email_verified')
                    if not status:
                        flash(
                            lazy_gettext('Such email is registered but hasn\'t been verified yet. '
                            'If it\'s your email please verify it, otherwise choose different credentials to log in or <a href="../register/">register</a>'),
                            'header')
                        return redirect(url_for('login'))
                else:
                    flash(
                        lazy_gettext('Sorry, we do not recognize this email address. Please choose different credentials or <a href="../register/">register</a>'),
                        'header')
                    return redirect(url_for('login'))

                # If Ok, check for a password
                pwd_should_be = users.find_one({'_id': docID})['password']
                if sha256_crypt.verify(password, pwd_should_be):
                    flash(lazy_gettext('Login successfull!'), 'header')

                    # Update session data
                    session['LoggedIn'] = 'yes'
                    session['Email'] = email

                    if which_traveler == 'All':
                        next_redirect = '/'
                    else:
                        next_redirect = '/{}/'.format(which_traveler)

                    # Update coockies
                    logged_in = request.cookies.get('LoggedIn', None)
                    if not logged_in:
                        expire_date = datetime.datetime.now()
                        expire_date = expire_date + datetime.timedelta(days=30)
                        redirect_to_index = redirect(next_redirect)
                        response = app.make_response(redirect_to_index)
                        response.set_cookie('LoggedIn', 'yes', expires=expire_date)
                        response.set_cookie('Email', email, expires=expire_date)
                        print('LoggedIn and Email cookies set')
                        return response
                    else:
                        print('LoggedIn and Email cookies already exist')
                        return redirect(next_redirect)

                # Invalid password
                else:
                    flash(lazy_gettext('Wrong password'), 'header')
                    return redirect(url_for('login'))

            # Login form did not validate on submit
            else:
                return render_template('login.html', loginform=loginform)
        # GET request
        else:
            return render_template('login.html', loginform=loginform)

    except Exception as e:
        print('login() exception: {}'.format(e))
        if which_traveler == 'All':
            return redirect(url_for('index'))
        else:
            return redirect(url_for('traveler'))


@app.route('/service/logout/')
@login_required
def logout():
    flash(lazy_gettext('You have been logged out'), 'header')
    OURTRAVELER = ft_functions.get_traveler()

    # Clear session
    session.clear()

    # and cookies
    expire_date = 0
    if OURTRAVELER == 'All':
        redirect_to = redirect(url_for('index'))
    else:
        redirect_to = redirect(url_for('traveler', OURTRAVELER=OURTRAVELER))
    response = app.make_response(redirect_to)
    response.set_cookie('LoggedIn', 'yes', expires=expire_date)
    response.set_cookie('Email', 'dummy', expires=expire_date)
    return response


@app.route('/', methods=['GET', 'POST']) # later '/' page will aggragate info for several travelers
def index():
    # Temporary
    OURTRAVELER = ft_functions.get_traveler()
    return redirect(url_for('traveler', OURTRAVELER=OURTRAVELER))


@app.route('/<OURTRAVELER>/', methods=['GET', 'POST'])
@csrf.exempt
def traveler(OURTRAVELER='Teddy'):

    print('Traveler: {}'.format(OURTRAVELER))
    print('Index!')

    try:
        whereisteddynowform = WhereisTeddyNow()
        subscribe2updatesform = HeaderEmailSubscription()

        # Check cookies for if user was logged in and set appropriate values to session
        if request.cookies.get('LoggedIn', None):
            session['LoggedIn'] = 'yes'
        if request.cookies.get('Email', None):
            email = request.cookies.get('Email')
            session['Email'] = email.replace('"', '')

        # Save our traveler's name to session
        if OURTRAVELER in ALL_TAVELERS:
            session['which_traveler'] = OURTRAVELER
        else:
            session['which_traveler'] = BASIC_TRAVELER

        # Check for preferred language
        user_language = get_locale()

        # Get travellers history
        whereteddywas = ft_functions.get_location_history(OURTRAVELER, PHOTO_DIR)
        locations_history = whereteddywas['locations_history']

        # Prepare a map
        teddy_map = Map(
            identifier="teddy_map",
            lat=whereteddywas['start_lat'],
            lng=whereteddywas['start_long'],
            zoom=8,
            language="en",
            style="height:480px;width:720px;margin:1;",
            markers=whereteddywas['mymarkers'],
            fit_markers_to_bounds=True
        )

        # Get journey summary
        journey_summary = ''
        travelled_so_far = ft_functions.get_journey_summary(OURTRAVELER)
        if not travelled_so_far:
            journey_summary = ''
        else:
            total_countries = travelled_so_far['total_countries']
            total_locations = travelled_so_far['total_locations']
            total_distance = travelled_so_far['total_distance']
            journey_duration = travelled_so_far['journey_duration']
            distance_from_home = travelled_so_far['distance_from_home']
            countries_visited_codes = travelled_so_far['countries_visited']
            countries_visited = ft_functions.translate_countries(countries_visited_codes, user_language)

            if total_countries == 1:
                countries_form = gettext('country')
            else:
                countries_form = gettext('countries')

            if journey_duration == 1:
                day_or_days = gettext('day')
            else:
                day_or_days = gettext('days')

            countries_list = (', ').join(countries_visited)

            journey_summary = gettext(
                'So far I\'ve checked in <b>{}</b> places located in <b>{}</b> {} ({}) and have been traveling for <b>{}</b> {}.\n\n'
                'I covered about <b>{}</b> km it total and currently I\'m nearly <b>{}</b> km from home').format(
                total_locations, total_countries, countries_form, countries_list, journey_duration,
                day_or_days, total_distance,
                distance_from_home)

        # POST-request
        if request.method == 'POST':
            print('Index-Post')

            print('Submitting new location...')
            # Check if user entered some location (required parameter) (data is passed from jQuery to Flask and
            # saved in session
            if 'geodata' not in session:
                flash(lazy_gettext('Please enter {}\'s location (current or on the photo)').format(OURTRAVELER),
                        'addlocation')
                return redirect(url_for('traveler', OURTRAVELER=OURTRAVELER, _anchor='updatelocation'))

            if whereisteddynowform.validate_on_submit():
                # Get user's input
                author = whereisteddynowform.author.data
                if author == '':
                    author = gettext("Anonymous")
                comment = whereisteddynowform.comment.data
                secret_code = whereisteddynowform.secret_code.data
                receive_email_updates = whereisteddynowform.getupdatesbyemail.data

                # Get photos (4 at max)
                photos = request.files.getlist('photo')
                photos_list = []
                for n in range(len(photos)):
                    if n<4:
                        path = ft_functions.photo_check_save(photos[n], OURTRAVELER)
                        if path != 'error':
                            photos[n].save('.' + PHOTO_DIR + OURTRAVELER + '/' + path)
                            photos_list.append(path)
                        else:
                            # At least one of images is invalid. Messages are flashed from photo_check_save()
                            return redirect(url_for('traveler', OURTRAVELER=OURTRAVELER, _anchor='updatelocation'))
                if len(photos)>4:
                    flash(
                        lazy_gettext('{}\'s locations are reposted to Twitter and thus can\'t have more than 4 images each. Only the first 4 photos were uploaded'.format(OURTRAVELER)),
                        'addlocation')

                # Save data to DB
                # Connect to DB 'TeddyGo'
                client = MongoClient()
                db = client.TeddyGo

                # Check secret code in collection 'travellers'
                collection_travellers = db.travellers
                teddys_sc_should_be = collection_travellers.find_one({"name": OURTRAVELER})['secret_code']
                if not sha256_crypt.verify(secret_code, teddys_sc_should_be):
                    flash(lazy_gettext('Invalid secret code'), 'addlocation')
                    return redirect(url_for('traveler', OURTRAVELER=OURTRAVELER, _anchor='updatelocation'))
                else:
                    # Prepare dictionary with new location info
                    geodata = session['geodata']

                    new_teddy_location = {
                        'author': author,
                        'channel': 'website',
                        'user_id_on_channel': None, # for website entry
                        'longitude': float(geodata.get('longitude')),
                        'latitude': float(geodata.get('latitude')),
                        'formatted_address': geodata.get('formatted_address'),
                        'locality':  geodata.get('locality'),
                        'administrative_area_level_1':  geodata.get('administrative_area_level_1'),
                        'country':  geodata.get('country'),
                        'place_id':  geodata.get('place_id'),
                        'comment': comment,
                        'photos': photos_list
                    }

                    # Connect to collection and insert document
                    collection_teddy = db[OURTRAVELER]
                    new_teddy_location_id = collection_teddy.insert_one(new_teddy_location).inserted_id

                    # Get the new secret code
                    new_code_generated = ft_functions.code_regenerate(OURTRAVELER)

                    if receive_email_updates:
                        save_user_as_subscriber(session['Email'], OURTRAVELER)

                    if new_code_generated:
                        # Flash the new code and send it to user's email
                        email = session['Email']
                        msg = Message(gettext("Fellowtraveler.club: new secret code - {}").format(new_code_generated),
                                      sender="mailvulgaris@gmail.com", recipients=[email])
                        msg.html = gettext(
                            "Hi!<br><br>You added a new {0}'s location, thanks. Secret code is being regenerated after every location and for adding the next location it will be:<br><br><b><h1>{1}</h1></b><br><br>It's recommended that you write it down to {0}'s notebook immediately (and obligatorily if you are going to pass {0} to somebody)<br><br>In case of any problems please write to <a href='mailto:iurii.dziuban@gmail.com'>iurii.dziuban@gmail.com</a><br><br>Thank you for participating in <a href='https://fellowtraveler.club'>fellowtraveler.club</a>").format(
                            OURTRAVELER, new_code_generated)
                        mail.send(msg)
                        flash(lazy_gettext('New location added! NEW SECRET CODE for adding the next location is {} (was sent to your email {}). Please write the new secret code into {}\'s notebook').format(new_code_generated, email, OURTRAVELER), 'header')

                    # Update journey summary
                    ft_functions.summarize_journey(OURTRAVELER)

                    # Post to Twitter
                    '''
                    newstatus = 'Teddy with {} in {}'.format(new_teddy_location['author'], new_teddy_location['formatted_address'])
                    if comment != '':
                        newstatus += '. {} wrote: {}'.format(new_teddy_location['author'], new_teddy_location['comment'])
                    status = twitter_api.PostUpdate(status=newstatus, media=new_teddy_location['photos'], latitude=new_teddy_location['latitude'],
                                                    longitude=new_teddy_location['longitude'], display_coordinates=True)
                    print(status.text)
                    '''

                    # Clear data from session
                    session.pop('geodata', None)

                    # Get travellers history
                    whereteddywas = ft_functions.get_location_history(OURTRAVELER, PHOTO_DIR)
                    locations_history = whereteddywas['locations_history']

                    # Prepare a map
                    teddy_map = Map(
                        identifier="teddy_map",
                        lat=whereteddywas['start_lat'],
                        lng=whereteddywas['start_long'],
                        zoom=8,
                        language="en",
                        style="height:480px;width:720px;margin:1;",
                        markers=whereteddywas['mymarkers'],
                        fit_markers_to_bounds=True
                    )

                    # Get journey summary
                    journey_summary = ''
                    travelled_so_far = ft_functions.get_journey_summary(OURTRAVELER)
                    if not travelled_so_far:
                        journey_summary = ''
                    else:
                        total_countries = travelled_so_far['total_countries']
                        total_locations = travelled_so_far['total_locations']
                        total_distance = travelled_so_far['total_distance']
                        journey_duration = travelled_so_far['journey_duration']
                        distance_from_home = travelled_so_far['distance_from_home']
                        countries_visited_codes = travelled_so_far['countries_visited']
                        countries_visited = ft_functions.translate_countries(countries_visited_codes, user_language)

                        if total_countries == 1:
                            countries_form = gettext('country')
                        else:
                            countries_form = gettext('countries')

                        if journey_duration == 1:
                            day_or_days = gettext('day')
                        else:
                            day_or_days = gettext('days')

                        countries_list = (', ').join(countries_visited)

                        journey_summary = gettext(
                            'So far I\'ve checked in <b>{}</b> places located in <b>{}</b> {} ({}) and have been traveling for <b>{}</b> {}.\n\n'
                            'I covered about <b>{}</b> km it total and currently I\'m nearly <b>{}</b> km from home').format(
                            total_locations, total_countries, countries_form, countries_list, journey_duration,
                            day_or_days, total_distance,
                            distance_from_home)

                    # If incorrect password
                    #return redirect(url_for('traveler', OURTRAVELER=OURTRAVELER, _anchor='updatelocation'))
                    return render_template('traveler.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform,
                                           locations_history=locations_history, teddy_map=teddy_map, journey_summary=journey_summary,
                                           language=user_language, traveler=OURTRAVELER, PHOTO_DIR=PHOTO_DIR)
            else:
                # If adding new location form didn't validate on submit
                # Clear geodata from session
                session.pop('geodata', None)

                return render_template('traveler.html', whereisteddynowform=whereisteddynowform,
                                       subscribe2updatesform=subscribe2updatesform, locations_history=locations_history,
                                       teddy_map=teddy_map, journey_summary=journey_summary, language=user_language,
                                       traveler=OURTRAVELER, scrolldown=True, PHOTO_DIR=PHOTO_DIR)
        # GET request
        else:
            # Get travellers history
            print('Index-Get')

            # Flash a disclaimer message and remember this in a cookie
            disclaimer_shown = request.cookies.get('DisclaimerShown')
            if not disclaimer_shown:
                flash(lazy_gettext('No, it\'s not a trick and supposed to be safe but please see <a href="/service/disclaimer/">disclaimer</a>'), 'header')
                # set a cookie so that disclaimer will be shown only once
                expire_date = datetime.datetime.now()
                expire_date = expire_date + datetime.timedelta(days=90)
                redirect_to_index = redirect('/')
                response = app.make_response(redirect_to_index)
                response.set_cookie('DisclaimerShown', 'yes', expires=expire_date)
                return response

            return render_template('traveler.html', whereisteddynowform=whereisteddynowform,
                                   subscribe2updatesform=subscribe2updatesform, locations_history=locations_history,
                                   teddy_map=teddy_map, journey_summary=journey_summary, language=user_language,
                                   traveler=OURTRAVELER, scrolldown=False, PHOTO_DIR=PHOTO_DIR)

    except Exception as e:
        print("error: {}".format(e))
        user_language = get_locale()
        return render_template('error.html', error=e, language=user_language)

@app.route("/get_geodata_from_gm", methods=["POST"])
@csrf.exempt
def get_geodata_from_gm():
    if request.method == "POST":
        mygeodata = request.get_json()
        # Retrieve 1) formatted address, 2) latitude, 3) longitude, 4) ['locality', 'political'] (~town), 5) ['administrative_area_level_1', 'political'] (~region/state), 6) ['country', 'political'] (country) and 7) place ID
        if mygeodata[0]:
            formatted_address = mygeodata[0].get('formatted_address', '')
            latitude = mygeodata[0].get('geometry').get('location').get('lat', 0) # unlikely that it will be in 0lat 0 long (somewhere in Atlantic Ocean)
            longitude = mygeodata[0].get('geometry').get('location').get('lng', 0)
            address_components = mygeodata[0].get('address_components', [])
            locality, administrative_area_level_1, country, place_id = None, None, None, None
            for address_component in address_components:
                types = address_component.get('types')
                short_name = address_component.get('short_name')
                #print("type: {}, short name: {}".format(types, short_name))
                if 'locality' in types:
                    locality = short_name
                elif 'administrative_area_level_1' in types:
                    administrative_area_level_1 = short_name
                elif 'country' in types:
                    country = short_name
            place_id = mygeodata[0].get('place_id')
            #print("Marker position on GMAPS ({}) was saved to session".format(mygeodata[0].get('formatted_address')))

        parsed_geodata = {
            'latitude': latitude,
            'longitude': longitude,
            'formatted_address': formatted_address,
            'locality': locality,
            'administrative_area_level_1': administrative_area_level_1,
            'country': country,
            'place_id': place_id
        }
        session['geodata'] = parsed_geodata
    return 'Geodata saved to session'

@app.route("/language/<lang_code>/")
@csrf.exempt
def user_language_to_coockie(lang_code):
    expire_date = datetime.datetime.now()
    expire_date = expire_date + datetime.timedelta(days=90)
    redirect_to_index = redirect('/')
    response = app.make_response(redirect_to_index)
    response.set_cookie('UserPreferredLanguage', lang_code, expires=expire_date)
    print('Preferred language, {}, was saved to coockie'.format(lang_code.upper()))
    return response

@app.route("/subscribe/", methods=["POST"])
@csrf.exempt
def direct_subscription():
    OURTRAVELER = ft_functions.get_traveler()
    print('OURTRAVELER: {}'.format(OURTRAVELER))

    subscribe2updatesform = HeaderEmailSubscription()

    if request.method == "POST":
        if subscribe2updatesform.validate_on_submit():
            email_entered = subscribe2updatesform.email4updates.data
            save_subscriber(email_entered, OURTRAVELER)
        else:
            flash(lazy_gettext("Please enter a valid e-mail address"), 'header')

    if OURTRAVELER == 'All':
        return redirect('/')
    else:
        return redirect('/{}/'.format(OURTRAVELER))


@app.route("/verify/<user_email>/<verification_code>")
@csrf.exempt
def verify_email(user_email, verification_code):
    '''
        Verification of new email for getting updates (DB TeddyGo >> subscribers)
        Unregistered users may subscribe to email updates
    '''
    next_redirect = '/'
    try:
        what_traveler = ft_functions.get_traveler()
        if what_traveler == 'All':
            whos_updates = "our travelers\'"
        else:
            whos_updates = "{}'s".format(what_traveler)
            next_redirect = '/{}/'.format(what_traveler)

        # Check if user's email exists in DB and is not unsubscribed
        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]})
        if not email_already_submitted:
            flash(lazy_gettext("Email {} was not found".format(user_email)), 'header')
            return redirect(next_redirect)

        # Find sha256_crypt-encrypted verification code in DB for a given user_email
        docID = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]}).get('_id')

        verification_code_should_be = subscribers.find_one({'_id': docID})['verification_code']

        # Compare it with the code submitted
        if not sha256_crypt.verify(verification_code, verification_code_should_be):
            # If invalid code - inform user
            flash(lazy_gettext('Sorry but you submitted an invalid verification code. Email address not verified'), 'header')
            return redirect(next_redirect)
        else:
            # If code Ok, check if email is not already verified
            if subscribers.find_one({'_id': docID})['verified'] == True:
                flash(lazy_gettext('Email address {} already verified'.format(user_email)), 'header')
                return redirect(next_redirect)
            else:
                # update the document in DB and inform user
                subscribers.update_one({'_id': docID}, {'$set': {'verified': True, 'unsubscribed': False}})
                flash(lazy_gettext('Email verified! Thanks for subscribing to {} location updates!'.format(whos_updates)), 'header')
                return redirect(next_redirect)
    except Exception as error:
        flash(lazy_gettext("Error happened ('{}')".format(error)), 'header')
        return redirect(next_redirect)

@app.route("/verify_user/<user_email>/<email_verification_code>")
@csrf.exempt
def verify_registration(user_email, email_verification_code):
    '''
        Verification of new user's email (DB TeddyGo >> users)
    '''
    try:
        what_traveler = ft_functions.get_traveler()
        if what_traveler == 'All':
            where_to_return = 'index'
        else:
            where_to_return = 'traveler'

        # Check if user's email exists in DB
        client = MongoClient()
        db = client.TeddyGo
        users = db.users
        email_already_submitted = users.find_one({"email": user_email})
        if not email_already_submitted:
            flash(lazy_gettext("Email {} was not found".format(user_email)), 'header')
            return redirect(url_for(where_to_return))

        # Find sha256_crypt-encrypted verification code in DB for a given user_email
        docID = users.find_one(
            {"$and": [{"email": user_email}, {'email_verified': {'$ne': True}}]}).get('_id')

        email_verification_code_should_be = users.find_one({'_id': docID})['email_verification_code']

        # Compare it with the code submitted
        if not sha256_crypt.verify(email_verification_code, email_verification_code_should_be):
            # If invalid code - inform user
            flash(lazy_gettext('Sorry but you submitted an invalid verification code. Email address not verified'), 'header')
            return redirect(url_for(where_to_return))
        else:
            # If code Ok, check if email is not already verified
            if users.find_one({'_id': docID})['email_verified'] == True:
                flash(lazy_gettext('Email address {} already verified'.format(user_email)), 'header')
                return redirect(url_for(where_to_return))
            else:
                # update the document in DB and inform user
                users.update_one({'_id': docID}, {'$set': {'email_verified': True}})

                flash(lazy_gettext(
                    'Email verified! Thanks for registration. If you\'ve got a fellow traveler you can add his/her new location now'),
                      'header')

                # Update coockies
                logged_in = request.cookies.get('LoggedIn', None)
                if not logged_in:
                    expire_date = datetime.datetime.now()
                    expire_date = expire_date + datetime.timedelta(days=30)
                    redirect_to_index = redirect('/')
                    response = app.make_response(redirect_to_index)
                    response.set_cookie('LoggedIn', 'yes', expires=expire_date)
                    response.set_cookie('Email', user_email, expires=expire_date)
                    print('LoggedIn and Email cookies set')
                    return response
                else:
                    print('LoggedIn and Email cookies already exist')
                    return redirect(url_for(where_to_return))
    except Exception as error:
        flash(lazy_gettext("Error happened ('{}')".format(error)), 'header')
        return redirect(url_for(where_to_return))

@app.route("/unsubscribe/<user_email>/<verification_code>")
@csrf.exempt
def unsubscribe(user_email, verification_code):
    where_to_return = '/'
    try:
        # Check which traveler user was watching
        what_traveler = ft_functions.get_traveler()
        if what_traveler == 'All':
            where_to_return = '/'
        else:
            where_to_return = '/{}/'.format(what_traveler)

        # Check if user's email exists in DB
        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]})
        if not email_already_submitted:
            flash(lazy_gettext("Email {} was not found".format(user_email)), 'header')
            return redirect(where_to_return)

        # Find sha256_crypt-encrypted verification code in DB for a given user_email
        docID = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]}).get('_id')
        verification_code_should_be = subscribers.find_one({'_id': docID})['verification_code']

        # Compare it with the code submitted
        if not sha256_crypt.verify(verification_code, verification_code_should_be):
            # If invalid code - inform user
            flash(lazy_gettext('Sorry but you submitted an invalid verification code. Unsubscription failed'), 'header')
            return redirect(where_to_return)
        else:
            # If code Ok, "soft"-delete the document
            subscribers.update_one({'_id': docID}, {'$set': {'unsubscribed': True}})
            flash(lazy_gettext('Email {} successfully unsubscribed'.format(user_email)), 'header')
            return redirect(where_to_return)
    except Exception as error:
        flash(lazy_gettext("Error happened ('{}')".format(error)), 'header')
        return redirect(where_to_return)

@app.route("/service/disclaimer/")
@csrf.exempt
def disclaimer():
    return render_template('disclaimer.html')

@app.route("/service/translate/")
@csrf.exempt
def translate():
    return render_template('translate.html')

@app.route("/service/support_project/")
@csrf.exempt
def support_project():
    return render_template('support_project.html')

@app.errorhandler(404)
@csrf.exempt
def page_not_found(error):
    # Check for preferred language
    return render_template('404.html'), 404

@app.errorhandler(413)
@csrf.exempt
def file_too_large(error):
    # Check for preferred language
    return render_template('413.html'), 413

@app.route("/webhook/", methods=['GET', 'POST'])
@csrf.exempt
def message_webhook():
    global LAST_COMMAND

    if request.method == 'GET':
        print('\nGET request')
        if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
            print('Verified!')
            return request.args.get("hub.challenge"), 200
        else:
            return 'Invalid verification token', 403

    if request.method == 'POST':

        output = request.get_json()

        #print("\nrequest.get_json(): ")
        #print(output)

        if output.get('object') == 'page':
            for entry in output.get('entry'):
                if entry.get('messaging'):
                    for message in entry.get('messaging'):
                        if message.get('message') or message.get('postback'):
                            # Get user ID
                            user_id = message.get('sender').get('id')

                            # Get user first name
                            user_first_name = get_user_first_name(user_id)
                            from_user = ''
                            if user_first_name:
                                from_user = user_first_name

                            # Text messages (emoji also get here - may filter out later)
                            if message.get('message'):
                                if not message.get('message').get('is_echo'):
                                    if message.get('message').get('text'):
                                        print('Text message received')
                                        #sender_action(user_id, 'mark_seen')
                                        #sender_action(user_id, 'typing_on')
                                        user_wrote = message.get('message').get('text')#.encode('unicode_escape')

                                        # Ugly solution agains duplicate responses to same user's commands (due to not confirming
                                        # messages receipt from FB in 20sec) - need to use some multythreading or smth like that
                                        command_number = message.get('message').get('seq')
                                        if command_number != LAST_COMMAND:
                                            LAST_COMMAND = command_number
                                            text_handler(user_id, from_user, user_wrote)

                                    # Attachments
                                    if message.get('message').get('attachments'):
                                        for attachment in message.get('message').get('attachments'):

                                            # Images (photos from camera, gifs, likes also get here)
                                            if attachment.get('type') == 'image' and not attachment.get('payload').get(
                                                    'sticker_id'):
                                                img_url = attachment.get('payload').get('url')
                                                #send_message(user_id, {'text': 'Img url "{}'.format(img_url)})
                                                #sender_action(user_id, 'mark_seen')
                                                #sender_action(user_id, 'typing_on')

                                                # Ugly solution agains duplicate responses to same user's commands (due to not confirming
                                                # messages receipt from FB in 20sec) - need to use some multythreading or smth like that
                                                command_number = message.get('message').get('seq')
                                                if command_number != LAST_COMMAND:
                                                    LAST_COMMAND = command_number
                                                    photo_handler(user_id, from_user, img_url)

                                            # Location
                                            elif attachment.get('type') == 'location':
                                                latitude = attachment.get('payload').get('coordinates').get('lat')
                                                longitude = attachment.get('payload').get('coordinates').get('long')
                                                #sender_action(user_id, 'mark_seen')
                                                #sender_action(user_id, 'typing_on')

                                                # Ugly solution agains duplicate responses to same user's commands (due to not confirming
                                                # messages receipt from FB in 20sec) - need to use some multythreading or smth like that
                                                command_number = message.get('message').get('seq')
                                                if command_number != LAST_COMMAND:
                                                    LAST_COMMAND = command_number
                                                    location_handler(user_id, from_user, latitude, longitude)

                                            # Other content types - audio, file, stickers (as images but with field 'sticker_id')
                                            else:
                                                print('Other content types')
                                                # Ugly solution agains duplicate responses to same user's commands (due to not confirming
                                                # messages receipt from FB in 20sec) - need to use some multythreading or smth like that
                                                command_number = message.get('message').get('seq')
                                                if command_number != LAST_COMMAND:
                                                    LAST_COMMAND = command_number
                                                    other_content_types_handler(user_id, from_user)


                            # Button clicks; persistent menu and 'Getting started' button send fixed postback in English,
                            # other buttons send postback = title in corresponding language, which is then passed to
                            # Dialogflow for NLU (thus the same commands as for these buttons can be triggered with usual text)
                            if message.get('postback') and message.get('postback').get('payload'):
                                button_payload = message.get('postback').get('payload')
                                #sender_action(user_id, 'mark_seen')
                                #sender_action(user_id, 'typing_on')
                                # Two main cases:
                                # 1. Persistent menu buttons and 'Getting started' button
                                if button_payload == 'GETTING_STARTED' or button_payload == 'START_TRIGGER':
                                    getting_started(user_id)

                                elif button_payload == 'FAQ':
                                    help(user_id)

                                elif button_payload == 'CHANGE_LANGUAGE':
                                    change_language(user_id)

                                elif button_payload == 'YOU_GOT_FELLOW_TRAVELER':
                                    you_got_fellowtraveler(user_id)

                                # 2. All other buttons
                                else:
                                    #sender_action(user_id, 'mark_seen')
                                    #sender_action(user_id, 'typing_on')
                                    button_payload = message.get('postback').get('payload')
                                    button_click_handler(user_id, from_user, button_payload)
        print('Sending 200 Ok response')
        return "Success", 200

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')