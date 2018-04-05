# -*- coding: utf-8 -*-

import os
from flask import Flask, render_template, url_for, request, redirect, flash, session, make_response, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, URL
from flask_wtf.csrf import CSRFProtect
from flask_wtf.recaptcha import RecaptchaField
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from flask_jsglue import JSGlue
from flask_googlemaps import GoogleMaps
from flask_googlemaps import Map
from flask_babel import Babel, gettext
import twitter

from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY, GOOGLE_MAPS_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN_KEY, TWITTER_ACCESS_TOKEN_SECRET

import tg_functions
RECAPTCHA_PUBLIC_KEY = '6LdlTE0UAAAAACb7TQc6yp12Klp0fzgifr3oF-BC'
LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'de': 'Deutsch',
    'fr': 'Français'
}

app = Flask(__name__)
app.config.from_object(__name__)
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY
GoogleMaps(app, key=GOOGLE_MAPS_API_KEY)
jsglue = JSGlue(app)
babel = Babel(app)
twitter_api = twitter.Api(consumer_key=TWITTER_CONSUMER_KEY, consumer_secret=TWITTER_CONSUMER_SECRET, access_token_key=TWITTER_ACCESS_TOKEN_KEY, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET)

@babel.localeselector
def get_locale():
    user_language = request.cookies.get('UserPreferredLanguage')
    if user_language:
        return user_language
    else:
        return request.accept_languages.best_match(LANGUAGES.keys())

@app.route('/index/')
@app.route('/') # later index page will aggragate info for several travellers
@csrf.exempt
def index():
    return render_template('draggablemarker.html')

@app.route("/get_geodata_from_gm", methods=["POST"])
@csrf.exempt
def get_geodata_from_gm():
    if request.method == "POST":
        mygeodata = request.get_json()
        print(str(mygeodata))
    return 'get_geodata_from_gm()'

@app.route("/language/<lang_code>")
@csrf.exempt
def user_language_to_coockie(lang_code):
    redirect_to_index = redirect('/')
    response = app.make_response(redirect_to_index)
    response.set_cookie('UserPreferredLanguage', lang_code)
    print('Preferred language, {}, was saved to coockie'.format(lang_code.upper()))
    return response

@app.errorhandler(404)
@csrf.exempt
def page_not_found(error):
    return render_template('404.html'), 404

@app.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    # Get request parameters
    req = request.get_json(silent=True, force=True)
    action = req.get('result').get('action')

    # TeddyGo - show timeline
    if action == "teddygo_show_timeline":
        location_iteration = tg_functions.show_location('Teddy', req)
        ourspeech = location_iteration['payload']
        output_context = location_iteration['updated_context']
        res = tg_functions.make_speech(ourspeech, action, output_context)

    else:
        # If the request is not of our actions throw an error
        res = {
            'speech': 'Something wrong happened',
            'displayText': 'Something wrong happened'
        }
    return make_response(jsonify(res))

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')