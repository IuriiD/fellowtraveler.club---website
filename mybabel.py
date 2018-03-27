#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, url_for, request, redirect, flash, session, g
from flask_babel import Babel, gettext

app = Flask(__name__)
babel = Babel(app)
app.secret_key = 'FLASK_SECRET_KEY'

LANGUAGES = {
    'en': 'English',
    'ry': 'Русский'
}

@app.route('/')
def main():
    flash(gettext('Hello man'))
    return render_template('babel.html')

@babel.localeselector
def get_locale():
    #return request.accept_languages.best_match(LANGUAGES.keys())
    return 'ru'

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')