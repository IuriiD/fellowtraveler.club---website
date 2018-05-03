# -*- coding: utf-8 -*-

import os
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
from flask_babel import Babel, gettext
from functools import wraps
import twitter
import uuid

from keys import FLASK_SECRET_KEY, RECAPTCHA_PRIVATE_KEY, GOOGLE_MAPS_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN_KEY, TWITTER_ACCESS_TOKEN_SECRET, MAIL_PWD

import tg_functions
RECAPTCHA_PUBLIC_KEY = '6LdlTE0UAAAAACb7TQc6yp12Klp0fzgifr3oF-BC'
SITE_URL = 'https://fellowtraveler.club'
LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'de': 'Deutsch',
    'fr': 'Français'
}

OURTRAVELLER = 'Teddy'
PHOTO_DIR = 'static/uploads/{}/'.format(OURTRAVELLER) # where photos from places visited are saved
SERVICE_IMG_DIR = 'static/uploads/{}/service/'.format(OURTRAVELLER) # where 'general info' images are saved (summary map, secret code example etc)

app = Flask(__name__)
app.config.from_object(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 20 # max photo to upload is 20Mb
csrf = CSRFProtect(app)
csrf.init_app(app)
app.secret_key = FLASK_SECRET_KEY
GoogleMaps(app, key=GOOGLE_MAPS_API_KEY)
jsglue = JSGlue(app)
babel = Babel(app)
twitter_api = twitter.Api(consumer_key=TWITTER_CONSUMER_KEY, consumer_secret=TWITTER_CONSUMER_SECRET, access_token_key=TWITTER_ACCESS_TOKEN_KEY, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET)

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
    author = StringField(gettext('Your name'), validators=[Length(-1, 50, gettext('Your name is a bit too long (50 characters max)'))])
    comment = TextAreaField(gettext('Add a comment'), validators=[Length(-1, 280, gettext('Sorry but comments are uploaded to Twitter and thus can\'t be longer than 280 characters'))])
    getupdatesbyemail = BooleanField('Get updates by email')
    secret_code = PasswordField(gettext('Secret code from the toy (required)'), validators=[DataRequired(gettext('Please enter the code which you can find on the label attached to the toy')),
                              Length(4, 4, gettext('Secret code must have 4 digits'))])
    #recaptcha = RecaptchaField()
    submit = SubmitField(gettext('Submit'))

class RegistrationForm(FlaskForm):
    email = StringField('Email Address', validators=[Length(6, 50), DataRequired(), Email('Please enter a valid e-mail address')])
    password = PasswordField('New Password', validators=[DataRequired(), EqualTo('confirm', message='Passwords must match')])
    confirm = PasswordField('Repeat Password')
    submit = SubmitField(gettext('Submit'))

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[Length(6, 50), DataRequired(), Email('Please enter a valid e-mail address')])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField(gettext('Submit'))

class HeaderEmailSubscription(FlaskForm):
    email4updates = StringField(gettext('Get updates by email:'), validators=[Optional(), Email(gettext('Please enter a valid e-mail address'))])
    emailsubmit = SubmitField(gettext('Subscribe'))

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'LoggedIn' in session:
            return f(*args, **kwargs)
        else:
            flash(gettext('You need to <a href="/login/">log in</a> first'),'header')
            return redirect(url_for('login'))
    return wrap

def notloggedin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'LoggedIn' in session:
            flash(gettext('You need to <a href="/logout/">log out</a> first'), 'header')
            return redirect(url_for('index'))
        else:
            return f(*args, **kwargs)
    return wrap

def save_subscriber(email_entered):
    '''
        Gets email address, checks if it's not already in subscribers' DB, saves it, sends a verification email and informs user with flashes
        Function not moved to function file not to move flask_mail setup block
    '''
    try:
        # Check if user's email is not already in DB
        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one({"$and": [{"email": email_entered}, {'unsubscribed': {'$ne': True}}]})

        if email_already_submitted:
            if email_already_submitted['verified']:
                flash(gettext("Email {} is already subscribed and verified".format(email_entered)), 'header')
                return {"status": "error", "message": "Email {} is already subscribed and verified".format(email_entered)}
            else:
                flash(gettext("Email {} is already subscribed but has not been verified yet".format(email_entered)), 'header')
                return {"status": "error",
                        "message": "Email {} is already subscribed but has not been verified yet".format(email_entered)}

        user_locale = get_locale()

        userid = str(uuid.uuid4())

        new_subscriber = {
            "email": email_entered,
            "locale": user_locale,
            "verified": False,
            "verification_code": sha256_crypt.encrypt(userid),
            "unsubscribed": None
        }

        verification_link = '{}/verify/{}/{}'.format(SITE_URL, email_entered, userid)
        unsubscription_link = '{}/unsubscribe/{}/{}'.format(SITE_URL, email_entered, userid)

        new_subscriber_id = subscribers.insert_one(new_subscriber).inserted_id

        msg = Message("Fellowtraveler.club: email verification link",
                      sender="mailvulgaris@gmail.com", recipients=[email_entered])
        msg.html = "Hi!<br><br>" \
                   "Thanks for subscribing to Teddy's location updates!<br>" \
                   "They won't be too often (not more than once a week).<br><br>" \
                   "Please verify your email address by clicking on the following link:<br><b>" \
                   "<a href='{0}' target='_blank'>{0}</a></b><br><br>" \
                   "If for any reason later you will decide to unsubscribe, please click on the following link:<br>" \
                   "<a href='{1}' target='_blank'>{1}</a>".format(verification_link, unsubscription_link)
        mail.send(msg)

        flash(gettext("A verification link has been sent to your email address. Please click on it to verify your email"), 'header')
        return {"status": "success",
                "message": "A verification link has been sent to your email address. Please click on it to verify your email"}
    except Exception as error:
        flash(gettext("Error happened ('{}')".format(error)), 'header')
        return {"status": "error",
                "message": "Error happened ('{}')".format(error)}

@babel.localeselector
def get_locale():
    user_language = request.cookies.get('UserPreferredLanguage')
    print("user_language: {}".format(user_language))
    print("autodetect_language: {}".format(request.accept_languages.best_match(LANGUAGES.keys())))
    if user_language != None:
        return user_language
    else:
        return request.accept_languages.best_match(LANGUAGES.keys())

@app.route('/register/', methods=['GET', 'POST'])
@notloggedin_required
@csrf.exempt
def register():
    try:
        form = RegistrationForm()
        subscribe2updatesform = HeaderEmailSubscription()

        # Check for preferred language
        user_language = get_locale()

        # registration data have been submitted (POST)
        if request.method == 'POST':
            if form.validate_on_submit():
                email = form.email.data
                password = sha256_crypt.encrypt(str(form.password.data))
                print('email: {}, pwd: {}'.format(email, form.password.data))

                client = MongoClient()
                db = client.TeddyGo
                users = db.users

                # Check if user with such email exists
                email_already_submitted = users.find_one({"email": email})

                if email_already_submitted:
                    if email_already_submitted['email_verified']:
                        flash(gettext("User with email {} is already registered. Please choose a different email address or <a href='/login'>log in</a>".format(email)), 'header')
                        return render_template('register.html', form=form, subscribe2updatesform=subscribe2updatesform, language=user_language)
                    else:
                        flash(gettext(
                            "User with email {} is already registered but email has not been verified yet".format(email)),
                              'header')
                        return render_template('register.html', form=form, subscribe2updatesform=subscribe2updatesform, language=user_language)
                else:
                    userid = str(uuid.uuid4())
                    email_verification_link = '{}/verify_email/{}/{}'.format(SITE_URL, email, userid)

                    users.insert_one(
                        {
                            'email': email,
                            'password': password,
                            'email_verified': False,
                            "email_verification_code": sha256_crypt.encrypt(userid)
                        }
                    )

                    msg = Message("Fellowtraveler.club: email verification link",
                                  sender="mailvulgaris@gmail.com", recipients=[email])
                    msg.html = "Hi! Thanks for registering on <b><a href='https://fellowtraveler.club'>fellowtraveler.club</a></b>.<br><br>" \
                               "Please verify your email address by clicking on the following link:<br><b><a href='{0}' target='_blank'>{0}</a></b><br><br>" \
                               "If it wasn't you please simply ignore this message".format(email_verification_link)
                    mail.send(msg)

                    flash('Almost finished. To complete registration please click on the verification link that has been sent to your email', 'header')

                    return redirect(url_for('index'))
            else:
                print('Registration form input did not validate')
                return render_template('register.html', form=form, subscribe2updatesform=subscribe2updatesform, language=user_language)
        # GET request for a registration form
        else:
            print('Post failed')
            return render_template('register.html', form=form, subscribe2updatesform=subscribe2updatesform, language=user_language)

    except Exception as e:
        print('register() exception: {}'.format(e))
        return redirect(url_for('index'))


@app.route('/login/', methods=['GET', 'POST'])
@notloggedin_required
@csrf.exempt
def login():
    try:
        loginform = LoginForm()
        subscribe2updatesform = HeaderEmailSubscription()

        # Check for preferred language
        user_language = get_locale()

        # login data have been submitted (POST)
        if request.method == 'POST' and loginform.validate_on_submit():
            email = loginform.email.data
            password = loginform.password.data

            client = MongoClient()
            db = client.TeddyGo
            users = db.users

            # check if email exist in DB and is verified
            docID = None
            if users.find_one({'email': email}):
                docID = users.find_one({'email': email}).get('_id')
                status = users.find_one({'_id': docID}).get('email_verified')
                if not status:
                    flash(
                        'Such email is registered but hasn\'t been verified yet. '
                        'If it\'s your email please verify it, otherwise choose different credentials to log in or <a href="/register/">register</a>',
                        'header')
                    return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)
            else:
                flash(
                    'Sorry, we do not recognize this email address. Please choose different credentials or <a href="/register/">register</a>',
                    'header')
                return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)

            # and then let's check for a password
            pwd_should_be = users.find_one({'_id': docID})['password']
            if sha256_crypt.verify(password, pwd_should_be):
                flash('Login successfull!',
                      'header')

                # Update session data
                session['LoggedIn'] = 'yes'
                session['Email'] = email

                # Update coockies
                logged_in = request.cookies.get('LoggedIn', None)
                if not logged_in:
                    expire_date = datetime.datetime.now()
                    expire_date = expire_date + datetime.timedelta(days=30)
                    redirect_to_index = redirect('/')
                    response = app.make_response(redirect_to_index)
                    response.set_cookie('LoggedIn', 'yes', expires=expire_date)
                    response.set_cookie('Email', email, expires=expire_date)
                    print('LoggedIn and Email cookies set')
                    return response
                else:
                    print('LoggedIn and Email cookies already exist')
                    return redirect(url_for('index'))

            # invalid password
            else:
                flash('Wrong password', 'header')
                return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)

        # the first (GET) request for a login form
        print()
        print('login.html')
        return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)

    except Exception as e:
        print('register() exception: {}'.format(e))
        return redirect(url_for('index'))


@app.route('/logout/')
@login_required
def logout():
    flash('You have been logged out', 'header')

    # Clear session
    session.clear()

    # and cookies
    expire_date = 0
    redirect_to_index = redirect('/')
    response = app.make_response(redirect_to_index)
    response.set_cookie('LoggedIn', 'yes', expires=expire_date)
    response.set_cookie('Email', 'dummy', expires=expire_date)
    return response



@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST']) # later index page will aggragate info for several travellers
#@app.route('/teddy/', methods=['GET', 'POST'])
@csrf.exempt
def index():
    print('Index!')
    try:
        traveller = 'Teddy'
        whereisteddynowform = WhereisTeddyNow()
        subscribe2updatesform = HeaderEmailSubscription()

        if request.cookies.get('LoggedIn', None):
            print('session["LoggedIn"] = "yes"')
            session['LoggedIn'] = 'yes'
        if request.cookies.get('Email', None):
            print("request.cookies.get('Email')")
            email = request.cookies.get('Email')
            session['Email'] = email.replace('"', '')

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
            user_language = get_locale()

            # Check if user entered some location (required parameter) (data is passed from jQuery to Flask and
            # saved in session
            if 'geodata' not in session:
                print('Here1')
                flash(gettext('Please enter Teddy\'s location (current or on the photo)'),
                        'addlocation')
                print('No data in session!')
                return render_template('index.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform,
                                       locations_history=locations_history, teddy_map=teddy_map, language=user_language, PHOTO_DIR=PHOTO_DIR)

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
                            photos[n].save(PHOTO_DIR + path)
                            photos_list.append(path)
                        else:
                            # At least one of images is invalid. Messages are flashed from photo_check_save()
                            return render_template('index.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform, locations_history=locations_history, teddy_map=teddy_map, language=user_language, PHOTO_DIR=PHOTO_DIR)
                if len(photos)>4:
                    flash(
                        gettext('Comments are uploaded to Twitter and thus can\'t have more than 4 images each. Only the first 4 photos were uploaded'),
                        'addlocation')

                # Save data to DB
                # Connect to DB 'TeddyGo'
                client = MongoClient()
                db = client.TeddyGo

                # Check secret code in collection 'travellers'
                collection_travellers = db.travellers
                teddys_sc_should_be = collection_travellers.find_one({"name": 'Teddy'})['secret_code']
                if not sha256_crypt.verify(secret_code, teddys_sc_should_be):
                    flash(gettext('Invalid secret code'), 'addlocation')
                    return render_template('index.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform, locations_history=locations_history, teddy_map=teddy_map, language=user_language, PHOTO_DIR=PHOTO_DIR)
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
                    collection_teddy = db[traveller]
                    new_teddy_location_id = collection_teddy.insert_one(new_teddy_location).inserted_id
                    print('new_teddy_location_id: {}'.format(new_teddy_location_id))

                    # Get the new secret code
                    new_code_generated = tg_functions.code_regenerate(traveller)

                    if new_code_generated:
                        # Flash the new code and send it to user's email
                        email = session['Email']
                        msg = Message("Fellowtraveler.club: new secret code - {}".format(new_code_generated),
                                      sender="mailvulgaris@gmail.com", recipients=[email])
                        msg.html = "Hi!<br><br>" \
                                   "You added a new {0}'s location, thanks. Secret code is being regenerated after every location and for adding the next location it will be:<br><br>" \
                                   "<b><h1>{1}</h1></b><br><br>" \
                                   "It's recommended that you write it down to {0}'s notebook immediately (and obligatorily if you are going to pass {0} to somebody)<br><br>" \
                                   "In case of any problems please write to <a href='mailto:iurii.dziuban@gmail.com'>iurii.dziuban@gmail.com</a><br><br>"\
                                   "Thank you for participating in <a href='https://fellowtraveler.club'>fellowtraveler.club</a>".format(traveller, new_code_generated)
                        mail.send(msg)
                        flash('New location added! NEW SECRET CODE for adding the next location is {} (was sent to your email {}). Please write the new secret code into {}\'s notebook'.format(new_code_generated, email, traveller), 'header')

                    # Update journey summary
                    tg_functions.summarize_journey('Teddy')

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

                    # Check for preferred language
                    user_language = get_locale()

                    return render_template('index.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform,
                                           locations_history=locations_history, teddy_map=teddy_map,
                                           language=user_language, PHOTO_DIR=PHOTO_DIR)
            else:
                print('Here3')
                # Clear data from session
                session.pop('geodata', None)

                return render_template('index.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform, locations_history=locations_history, teddy_map=teddy_map, language=user_language, PHOTO_DIR=PHOTO_DIR)

        # GET request
        # Get travellers history (will be substituted with timeline embedded from Twitter )
        print('Index-Get')

        # Flashing disclaimer message
        disclaimer_shown = request.cookies.get('DisclaimerShown')
        if not disclaimer_shown:
            flash(gettext(
                'No, it\'s not a trick and supposed to be safe but please see <a href="">disclaimer</a>'),
                  'header')
            # set a cookie so that disclaimer will be shown only once
            expire_date = datetime.datetime.now()
            expire_date = expire_date + datetime.timedelta(days=90)
            redirect_to_index = redirect('/')
            response = app.make_response(redirect_to_index)
            response.set_cookie('DisclaimerShown', 'yes', expires=expire_date)
            return response

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
        user_language = get_locale()
        return render_template('index.html', whereisteddynowform=whereisteddynowform, subscribe2updatesform=subscribe2updatesform, locations_history=locations_history, teddy_map=teddy_map, language=user_language, PHOTO_DIR=PHOTO_DIR)

    except Exception as error:
        print("error: {}".format(error))
        return render_template('error.html', error=error, subscribe2updatesform=subscribe2updatesform, language=user_language)

@app.route("/get_geodata_from_gm", methods=["POST"])
@csrf.exempt
def get_geodata_from_gm():
    print("get_geodata_from_gm!")
    if request.method == "POST":
        mygeodata = request.get_json()
        # Retrieve 1) formatted address, 2) latitude, 3) longitude, 4) ['locality', 'political'] (~town), 5) ['administrative_area_level_1', 'political'] (~region/state), 6) ['country', 'political'] (country) and 7) place ID
        if mygeodata[0]:
            formatted_address = mygeodata[0].get('formatted_address')
            latitude = mygeodata[0].get('geometry').get('location').get('lat', 0) # unlikely that it will be in 0lat 0 long (somewhere in Atlantic Ocean)
            longitude = mygeodata[0].get('geometry').get('location').get('lng', 0)
            address_components = mygeodata[0].get('address_components')
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

        parsed_geodata = {
            'latitude': latitude,
            'longitude': longitude,
            'formatted_address': formatted_address,
            'locality': locality,
            'administrative_area_level_1': administrative_area_level_1,
            'country': country,
            'place_id': place_id
        }
        #print('Geodata: {}'.format(parsed_geodata))
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
    subscribe2updatesform = HeaderEmailSubscription()
    if request.method == "POST" and subscribe2updatesform.validate_on_submit():
        email_entered = subscribe2updatesform.email4updates.data
    else:
        flash(gettext("Please enter a valid e-mail address"), 'header')
        return redirect(url_for('index'))
    result = save_subscriber(email_entered)
    return redirect(url_for('index'))

@app.route("/verify/<user_email>/<verification_code>")
@csrf.exempt
def verify_email(user_email, verification_code):
    '''
        Verification of new email for getting updates (DB TeddyGo >> subscribers)
    '''
    try:
        # Check if user's email exists in DB and is not unsubscribed
        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]})
        if not email_already_submitted:
            flash(gettext("Email {} was not found".format(user_email)), 'header')
            return redirect(url_for('index'))

        # Find sha256_crypt-encrypted verification code in DB for a given user_email
        docID = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]}).get('_id')
        print("##### docID: {}".format(docID))
        print("##### Verif code: {}".format(subscribers.find_one({'_id': docID})['verification_code']))
        print("##### Verif code should be: {}".format(verification_code))

        verification_code_should_be = subscribers.find_one({'_id': docID})['verification_code']

        # Compare it with the code submitted
        if not sha256_crypt.verify(verification_code, verification_code_should_be):
            # If invalid code - inform user
            flash(gettext('Sorry but you submitted an invalid verification code. Email address not verified'), 'header')
            return redirect(url_for('index'))
        else:
            # If code Ok, check if email is not already verified
            if subscribers.find_one({'_id': docID})['verified'] == True:
                flash(gettext('Email address {} already verified'.format(user_email)), 'header')
                return redirect(url_for('index'))
            else:
                # update the document in DB and inform user
                subscribers.update_one({'_id': docID}, {'$set': {'verified': True, 'unsubscribed': False}})
                flash(gettext('Email verified! Thanks for subscribing to Teddy\'s location updates!'), 'header')
                return redirect(url_for('index'))
    except Exception as error:
        flash(gettext("Error happened ('{}')".format(error)), 'header')
        return redirect(url_for('index'))

@app.route("/verify_email/<user_email>/<email_verification_code>")
@csrf.exempt
def verify_registration(user_email, email_verification_code):
    '''
        Verification of new user's email (DB TeddyGo >> users)
    '''
    try:
        # Check if user's email exists in DB
        client = MongoClient()
        db = client.TeddyGo
        users = db.users
        email_already_submitted = users.find_one({"email": user_email})
        if not email_already_submitted:
            flash(gettext("Email {} was not found".format(user_email)), 'header')
            return redirect(url_for('index'))

        # Find sha256_crypt-encrypted verification code in DB for a given user_email
        docID = users.find_one(
            {"$and": [{"email": user_email}, {'email_verified': {'$ne': True}}]}).get('_id')

        email_verification_code_should_be = users.find_one({'_id': docID})['email_verification_code']

        # Compare it with the code submitted
        if not sha256_crypt.verify(email_verification_code, email_verification_code_should_be):
            # If invalid code - inform user
            flash(gettext('Sorry but you submitted an invalid verification code. Email address not verified'), 'header')
            return redirect(url_for('index'))
        else:
            # If code Ok, check if email is not already verified
            if users.find_one({'_id': docID})['email_verified'] == True:
                flash(gettext('Email address {} already verified'.format(user_email)), 'header')
                return redirect(url_for('index'))
            else:
                # update the document in DB and inform user
                users.update_one({'_id': docID}, {'$set': {'email_verified': True}})

                flash(gettext(
                    'Email verified! Thanks for registration. If you have Teddy you can add his new location now'),
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
                    return redirect(url_for('index'))
    except Exception as error:
        flash(gettext("Error happened ('{}')".format(error)), 'header')
        return redirect(url_for('index'))

@app.route("/unsubscribe/<user_email>/<verification_code>")
@csrf.exempt
def unsubscribe(user_email, verification_code):
    try:
        # Check if user's email exists in DB
        client = MongoClient()
        db = client.TeddyGo
        subscribers = db.subscribers
        email_already_submitted = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]})
        if not email_already_submitted:
            flash(gettext("Email {} was not found".format(user_email)), 'header')
            return redirect(url_for('index'))

        # Find sha256_crypt-encrypted verification code in DB for a given user_email
        docID = subscribers.find_one(
            {"$and": [{"email": user_email}, {'unsubscribed': {'$ne': True}}]}).get('_id')
        verification_code_should_be = subscribers.find_one({'_id': docID})['verification_code']


        # Compare it with the code submitted
        if not sha256_crypt.verify(verification_code, verification_code_should_be):
            # If invalid code - inform user
            flash(gettext('Sorry but you submitted an invalid verification code. Unsubscription failed'), 'header')
            return redirect(url_for('index'))
        else:
            # If code Ok, "soft"-delete the document
            subscribers.update_one({'_id': docID}, {'$set': {'unsubscribed': True}})
            flash(gettext('Email successfully unsubscribed'), 'header')
            return redirect(url_for('index'))
    except Exception as error:
        flash(gettext("Error happened ('{}')".format(error)), 'header')
        return redirect(url_for('index'))

@app.errorhandler(404)
@csrf.exempt
def page_not_found(error):
    subscribe2updatesform = HeaderEmailSubscription()
    # Check for preferred language
    user_language = get_locale()
    return render_template('404.html', subscribe2updatesform=subscribe2updatesform, language=user_language), 404

@app.errorhandler(413)
@csrf.exempt
def file_too_large(error):
    subscribe2updatesform = HeaderEmailSubscription()
    # Check for preferred language
    user_language = get_locale()
    return render_template('413.html', subscribe2updatesform=subscribe2updatesform, language=user_language), 413

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