# -*- coding: utf-8 -*-

import datetime
from flask import Flask, render_template, url_for, request, redirect, flash, session, make_response, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, URL, Email, Optional, EqualTo
from flask_wtf.csrf import CSRFProtect
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

from keys import (FLASK_SECRET_KEY,
                  RECAPTCHA_PRIVATE_KEY,
                  RECAPTCHA_PUBLIC_KEY,
                  GOOGLE_MAPS_API_KEY,
                  TWITTER_CONSUMER_KEY,
                  TWITTER_CONSUMER_SECRET,
                  TWITTER_ACCESS_TOKEN_KEY,
                  TWITTER_ACCESS_TOKEN_SECRET,
                  MAIL_PWD)

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

app = Flask(__name__)
app.config.from_object(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 20 # max photo to upload is 20Mb
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY
GoogleMaps(app, key=GOOGLE_MAPS_API_KEY)
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
            print("Marker position on GMAPS ({}) was saved to session".format(mygeodata[0].get('formatted_address')))

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

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')