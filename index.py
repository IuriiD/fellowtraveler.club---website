#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from flask import Flask, render_template, url_for, request, redirect, flash, session
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
import twitter

from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY, GOOGLE_MAPS_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN_KEY, TWITTER_ACCESS_TOKEN_SECRET

from tg_functions import photo_check_save, get_location_history
RECAPTCHA_PUBLIC_KEY = '6LdlTE0UAAAAACb7TQc6yp12Klp0fzgifr3oF-BC'

app = Flask(__name__)
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY
jsglue = JSGlue(app)
GoogleMaps(app, key=GOOGLE_MAPS_API_KEY)
twitter_api = twitter.Api(consumer_key=TWITTER_CONSUMER_KEY, consumer_secret=TWITTER_CONSUMER_SECRET, access_token_key=TWITTER_ACCESS_TOKEN_KEY, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET)

class WhereisTeddyNow(FlaskForm):
    author = StringField('Your name', validators=[Length(-1, 50, 'Your name is a bit too long (50 characters max)')])
    email = StringField('Your email address', validators=[Length(-1, 50, 'Your email addres is a bit too long (60 characters max)')])
    comment = TextAreaField('Add a comment', validators=[Length(-1, 280, 'Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters')])
    media_url = StringField('',
                        validators=[Length(-1, 200, 'Invalid URL')])
    secret_code = PasswordField('Secret code from the toy (required)', validators=[DataRequired('Please enter the code which you can find on the label attached to the toy'),
                              Length(6, 6, 'Secret code must have 6 digits')])
    get_updates_by_email = BooleanField('Get updates of Teddy\'s location by email')
    #recaptcha = RecaptchaField()
    submit = SubmitField('Submit')

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

            # Get travellers history (will be substituted with timeline embedded from Twitter )
            whereteddywas = get_location_history(traveller)
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

            # Check if user entered some location (required parameter) (data is passed from jQuery to Flask and
            # saved in session
            if 'latitude' not in session:
                print('Here1')
                flash('Please enter Teddy\'s location (current or on the photo)',
                        'alert alert-warning alert-dismissible fade show')
                print('No data in session!')
                return render_template('index.html', whereisteddynowform=whereisteddynowform,
                                       locations_history=locations_history, teddy_map=teddy_map)

            # Get user's input
            print('Here2')
            if whereisteddynowform.validate_on_submit():
                print('Here4')
                # Get user's input
                author = whereisteddynowform.author.data
                if author == '':
                    author = "Anonymous"
                #location = whereisteddynowform.location.data
                comment = whereisteddynowform.comment.data
                secret_code = whereisteddynowform.secret_code.data

                # Get photos (4 at max)
                photos = request.files.getlist('photo')
                photos_list = []
                for n in range(len(photos)):
                    if n<4:
                        path = photo_check_save(photos[n])
                        if path != 'error':
                            photos[n].save(os.path.join(app.static_folder, path))
                            photos_list.append(path)
                        else:
                            # At least one of images is invalid. Messages are flashed from photo_check_save()
                            return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map)
                if len(photos)>4:
                    flash(
                        'Comments are uploaded to Twitter and thus can\'t have more than 4 images each. Only the first 4 photos were uploaded',
                        'alert alert-warning alert-dismissible fade show')

                # Save data to DB
                # Connect to DB 'TeddyGo'
                client = MongoClient()
                db = client.TeddyGo

                # Check secret code in collection 'travellers'
                collection_travellers = db.travellers
                teddys_sc_should_be = collection_travellers.find_one({"name": 'Teddy'})['secret_code']
                if not sha256_crypt.verify(secret_code, teddys_sc_should_be):
                    flash('Invalid secret code', 'alert alert-warning alert-dismissible fade show')
                    return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map)
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
                    # Clear data from session
                    session.pop('latitude', None)
                    session.pop('longitude', None)
                    session.pop('formatted_address', None)
            else:
                print('Here3')
                return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map)

        # GET request
        # Get travellers history (will be substituted with timeline embedded from Twitter )
        print('Index-Get')

        # Get travellers history (will be substituted with timeline embedded from Twitter )
        whereteddywas = get_location_history(traveller)
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
        return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history, teddy_map=teddy_map)

    except Exception as error:
        return redirect(url_for('index'))

@app.route("/get_geodata_from_gm", methods=["POST"])
@csrf.exempt
def get_geodata_from_gm():
    if request.method == "POST":
        latitude = request.json.get('lat')
        longitude = request.json.get('lng')
        address = request.json.get('addr')
        session['latitude'] = latitude
        session['longitude'] = longitude
        session['formatted_address'] = address
    return 'get_geodata_from_gm()'

@app.errorhandler(404)
@csrf.exempt
def page_not_found(error):
    return render_template('404.html'), 404

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')