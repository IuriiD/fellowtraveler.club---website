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

class WhereisTeddyNow(FlaskForm):
    author = StringField(gettext('Your name'), validators=[Length(-1, 50, gettext('Your name is a bit too long (50 characters max)'))])
    comment = TextAreaField(gettext('Add a comment'), validators=[Length(-1, 280, gettext('Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters'))])
    secret_code = PasswordField(gettext('Secret code from the toy (required)'), validators=[DataRequired(gettext('Please enter the code which you can find on the label attached to the toy')),
                              Length(6, 6, gettext('Secret code must have 6 digits'))])
    #recaptcha = RecaptchaField()
    submit = SubmitField(gettext('Submit'))

@babel.localeselector
def get_locale():
    user_language = request.cookies.get('UserPreferredLanguage')
    if user_language:
        return user_language
    else:
        return request.accept_languages.best_match(LANGUAGES.keys())

@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST']) # later index page will aggragate info for several travellers
#@app.route('/teddy/', methods=['GET', 'POST'])
@csrf.exempt
def index():
    print('Index!')
    try:
        traveller = 'Teddy'
        whereisteddynowform = WhereisTeddyNow()

        # POST-request
        if request.method == 'POST':
            print('Index-Post')

            # Get travellers history
            whereteddywas = tg_functions.get_location_history(traveller)
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
                fit_markers_to_bounds = True
            )

            # Check for preferred language
            user_language = request.cookies.get('UserPreferredLanguage')
            if not user_language:
                user_language = 'en'

            # Check if user entered some location (required parameter) (data is passed from jQuery to Flask and
            # saved in session
            if 'latitude' not in session:
                print('Here1')
                flash(gettext('Please enter Teddy\'s location (current or on the photo)'),
                        'alert alert-warning alert-dismissible fade show')
                print('No data in session!')
                return render_template('index.html', whereisteddynowform=whereisteddynowform,
                                       locations_history=locations_history, teddy_map=teddy_map, language=user_language)

            # Get user's input
            print('Here2')
            if whereisteddynowform.validate_on_submit():
                print('Here4')
                # Get user's input
                author = whereisteddynowform.author.data
                if author == '':
                    author = gettext("Anonymous")
                #location = whereisteddynowform.location.data
                comment = whereisteddynowform.comment.data
                secret_code = whereisteddynowform.secret_code.data

                # Get photos (4 at max)
                photos = request.files.getlist('photo')
                photos_list = []
                for n in range(len(photos)):
                    if n<4:
                        path = tg_functions.photo_check_save(photos[n])
                        if path != 'error':
                            photos[n].save(os.path.join(app.static_folder, path))
                            photos_list.append(path)
                        else:
                            # At least one of images is invalid. Messages are flashed from photo_check_save()
                            return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map, language=user_language)
                if len(photos)>4:
                    flash(
                        gettext('Comments are uploaded to Twitter and thus can\'t have more than 4 images each. Only the first 4 photos were uploaded',
                        'alert alert-warning alert-dismissible fade show'))

                # Save data to DB
                # Connect to DB 'TeddyGo'
                client = MongoClient()
                db = client.TeddyGo

                # Check secret code in collection 'travellers'
                collection_travellers = db.travellers
                teddys_sc_should_be = collection_travellers.find_one({"name": 'Teddy'})['secret_code']
                if not sha256_crypt.verify(secret_code, teddys_sc_should_be):
                    flash(gettext('Invalid secret code', 'alert alert-warning alert-dismissible fade show'))
                    return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map, language=user_language)
                else:
                    # Prepare dictionary with new location info
                    new_teddy_location = {
                        'author': author,
                        'longitude': float(session['longitude']),
                        'latitude': float(session['latitude']),
                        'formatted_address': session['formatted_address'],
                        'comment': comment,
                        'photos': photos_list
                    }

                    # Connect to collection and insert document
                    collection_teddy = db[traveller]
                    new_teddy_location_id = collection_teddy.insert_one(new_teddy_location).inserted_id
                    print('new_teddy_location_id: {}'.format(new_teddy_location_id))

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
                    session.pop('latitude', None)
                    session.pop('longitude', None)
                    session.pop('formatted_address', None)

                    # Get travellers history
                    whereteddywas = tg_functions.get_location_history(traveller)
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

                    return render_template('index.html', whereisteddynowform=whereisteddynowform,
                                           locations_history=locations_history, teddy_map=teddy_map,
                                           language=user_language)
            else:
                print('Here3')
                return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map, language=user_language)

        # GET request
        # Get travellers history (will be substituted with timeline embedded from Twitter )
        print('Index-Get')

        # Get travellers history (will be substituted with timeline embedded from Twitter )
        whereteddywas = tg_functions.get_location_history(traveller)
        print('whereteddywas!')
        locations_history = whereteddywas['locations_history']
        print('locations_history!')

        # Prepare a map
        teddy_map = Map(
            identifier="teddy_map",
            lat=whereteddywas['start_lat'],
            lng=whereteddywas['start_long'],
            zoom=8,
            language="en",
            style="height:480px;width:700px;margin:1;",
            markers=whereteddywas['mymarkers'],
            fit_markers_to_bounds=True
        )
        print('teddy_map!')
        # Check for preferred language
        user_language = request.cookies.get('UserPreferredLanguage')
        if not user_language:
            user_language = 'en'
        print("user_language: {}".format(user_language))
        return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map, language=user_language)

    except Exception as error:
        print("error: {}".format(error))
        return "error: {}".format(error)

@app.route("/get_geodata_from_gm", methods=["POST"])
@csrf.exempt
def get_geodata_from_gm():
    print("get_geodata_from_gm!")
    if request.method == "POST":
        mygeodata = request.get_json()
        latitude = mygeodata.get('lat')
        longitude = mygeodata.get('lng')
        address = mygeodata.get('addr')
        session['latitude'] = latitude
        session['longitude'] = longitude
        session['formatted_address'] = address
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