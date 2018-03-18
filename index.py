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
from random import randint

from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY
from tg_functions import valid_url_extension, valid_url_mimetype, image_exists

RECAPTCHA_PUBLIC_KEY = '6LdlTE0UAAAAACb7TQc6yp12Klp0fzgifr3oF-BC'

app = Flask(__name__)
app.config.from_object(__name__)
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY

class WhereisTeddyNow(FlaskForm):
    author = StringField('Please name yourself', validators=[DataRequired('Please name yourself'),
                              Length(2, 50, 'Please enter a name 2-50 characters long')])
    location = StringField('Where is Teddy now?', validators=[DataRequired('Please define at least a country and city'),
                              Length(2, 120, 'Location name shouldn\'t be longer than 120 characters')])
    photo = FileField('Upload a photo')
    comment = TextAreaField('Add some comment (optionally)', validators=[Length(-1, 280, 'Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters')])
    secret_code = PasswordField('Secret code from the toy', validators=[DataRequired('Please enter the code which you can find on the label attached to the toy'),
                              Length(6, 6, 'Wrong secret code')])
    recaptcha = RecaptchaField()
    submit = SubmitField('Submit')

@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
@csrf.exempt
def index():
    try:
        whereisteddynowform = WhereisTeddyNow()

        # POST-request
        if request.method == 'POST' and whereisteddynowform.validate_on_submit():
            # Prepare DB
            client = MongoClient()
            db = client.TeddyGo
            collection = db.Teddy

            author = whereisteddynowform.author.data
            location = whereisteddynowform.location.data
            comment = whereisteddynowform.comment.data

            photo_filename = request.files['photo'].filename
            flash(
                'photo_filename: {}'.format(photo_filename),
                'alert alert-warning alert-dismissible fade show')
            if valid_url_extension(photo_filename) and valid_url_mimetype(photo_filename):
                file_name_wo_extension = os.path.splitext(photo_filename)[0]
                file_extension = os.path.splitext(photo_filename)[1]
                path = 'uploads/' + file_name_wo_extension + '-' + str(randint(1, 10000)) + file_extension
                request.files['photo'].save(os.path.join(app.static_folder, path))
            else:
                flash(
                    'Invalid image extension (not ".jpg", ".jpeg", ".png", ".gif" or ".bmp") or invalid image format',
                    'alert alert-warning alert-dismissible fade show')
                return render_template('index.html', whereisteddynowform=whereisteddynowform)
        else:
            flash(
                'Invalid data was entered',
                'alert alert-warning alert-dismissible fade show')
            return render_template('index.html', whereisteddynowform=whereisteddynowform)
        # GET request
        wheewisteddynowform = WhereisTeddyNow()
        return render_template('index.html', whereisteddynowform=whereisteddynowform)

    except Exception as error:
        return redirect(url_for('index'))

@app.errorhandler(404)
@csrf.exempt
def page_not_found(error):
    return render_template('404.html'), 404

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')