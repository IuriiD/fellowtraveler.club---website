#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from flask import Flask, render_template, url_for, request, redirect, flash, session
from flask_wtf import FlaskForm
from wtforms import FileField, StringField, SubmitField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Length
from flask_wtf.csrf import CSRFProtect
from flask_wtf.recaptcha import RecaptchaField
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from flask_jsglue import JSGlue
#from random import randint
#from flask_googlemaps import GoogleMaps
#from flask_googlemaps import Map

from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY, GOOGLE_MAPS_API_KEY
from tg_functions import photo_check_save, get_location_history
RECAPTCHA_PUBLIC_KEY = '6LdlTE0UAAAAACb7TQc6yp12Klp0fzgifr3oF-BC'

app = Flask(__name__)
#GoogleMaps(app, key=GOOGLE_MAPS_API_KEY)
jsglue = JSGlue(app)
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY

class WhereisTeddyNow(FlaskForm):
    author = StringField('Please state your name', validators=[Length(-1, 50, 'Your name is a bit too long (50 characters max)')])
    #location = StringField('Where is Teddy now? (required)', validators=[DataRequired('Please define at least a country and city'),
    #                          Length(2, 120, 'Location name shouldn\'t be longer than 120 characters')])
    comment = TextAreaField('Add a comment', validators=[Length(-1, 280, 'Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters')])
    secret_code = PasswordField('Secret code from the toy (required)', validators=[DataRequired('Please enter the code which you can find on the label attached to the toy'),
                              Length(6, 6, 'Secret code must have 6 digits')])
    #recaptcha = RecaptchaField()
    submit = SubmitField('Submit')

@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST']) # later index page will aggragate info for several travellers
@app.route('/teddy/', methods=['GET', 'POST'])
@csrf.exempt
def index():
    try:
        traveller = 'Teddy'
        whereisteddynowform = WhereisTeddyNow()

        # POST-request
        if request.method == 'POST':
            # Get travellers history (will be substituted with timeline embedded from Twitter )
            locations_history = get_location_history(traveller)

            # Get user's input
            if whereisteddynowform.validate_on_submit():
                # Get user's input
                author = whereisteddynowform.author.data
                if author == '':
                    author = "Anonymous"
                location = whereisteddynowform.location.data
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
                            return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history)
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
                    return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history)
                else:
                    # Prepare dictionary with new location info
                    new_teddy_location = {
                        'author': author,
                        'location': location,
                        'comment': comment,
                        'photos': photos_list
                    }

                    # Connect to collection and insert document
                    collection_teddy = db[traveller]
                    new_teddy_location_id = collection_teddy.insert_one(new_teddy_location).inserted_id
            else:
                return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history)

        # GET request
        # Get travellers history (will be substituted with timeline embedded from Twitter )
        locations_history = get_location_history(traveller)
        return render_template('index.html', whereisteddynowform=whereisteddynowform, locations_history=locations_history)

    except Exception as error:
        return redirect(url_for('index'))

@app.route("/get_lat_lng", methods=["POST"])
@csrf.exempt
def get_lat_lng():
    print('Flask!')
    if request.method == "POST":
        print('It\'s POST!')
        latitude = request.json.get('lat')
        longitude = request.json.get('lng')
        address = request.json.get('addr')
        print('{}, {}, {}'.format(latitude, longitude, address))
    return 'Post triggered'

@app.errorhandler(404)
@csrf.exempt
def page_not_found(error):
    return render_template('404.html'), 404

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')