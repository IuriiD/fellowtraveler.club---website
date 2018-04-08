# -*- coding: utf-8 -*-

from flask import Flask, render_template, url_for, request, redirect, flash, session, make_response, jsonify
from flask_uploads import UploadSet, IMAGES, configure_uploads
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, URL
from flask_wtf.csrf import CSRFProtect
from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY, GOOGLE_MAPS_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN_KEY, TWITTER_ACCESS_TOKEN_SECRET

app = Flask(__name__)
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY

# Configure the image uploading via Flask-Uploads
images = UploadSet('images', IMAGES)
configure_uploads(app, images)

class WhereisTeddyNow(FlaskForm):
    author = StringField(gettext('Your name'), validators=[Length(-1, 50, gettext('Your name is a bit too long (50 characters max)'))])
    comment = TextAreaField(gettext('Add a comment'), validators=[Length(-1, 280, gettext('Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters'))])
    secret_code = PasswordField(gettext('Secret code from the toy (required)'), validators=[DataRequired(gettext('Please enter the code which you can find on the label attached to the toy')),
                              Length(6, 6, gettext('Secret code must have 6 digits'))])
    #recaptcha = RecaptchaField()
    submit = SubmitField(gettext('Submit'))


# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')