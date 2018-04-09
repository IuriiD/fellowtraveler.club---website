# -*- coding: utf-8 -*-

from flask import Flask, render_template, url_for, request, redirect, flash, session, make_response, jsonify
from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY, GOOGLE_MAPS_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN_KEY, TWITTER_ACCESS_TOKEN_SECRET

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Configure the image uploading via Flask-Uploads
@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST']) # later index page will aggragate info for several travellers
def index():
    flash("Message for flash 1 LOLOLOLO", 'header')
    flash("Message for flash 1 GOGOGOGOGOG", 'header')
    flash("Message for flash 2 OPOO", 'info')
    return render_template('flash2.html')
# 'alert alert-warning alert-dismissible fade show'
# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')