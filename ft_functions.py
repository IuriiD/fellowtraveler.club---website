# -*- coding: utf-8 -*-

import os
from flask import request, flash, url_for, redirect, session, make_response
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
import requests
from pymongo import MongoClient
import mimetypes
from random import randint
from flask_babel import Babel, gettext, lazy_gettext
import datetime
#import uuid
#from ft import send_mail

from keys import FLASK_SECRET_KEY, TG_TOKEN, DF_TOKEN, GOOGLE_MAPS_API_KEY, MAIL_PWD

VALID_IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".JPG",
    ".JPEG",
    ".PNG",
    ".GIF",
    ".BMP"
]

VALID_IMAGE_MIMETYPES = [
    "image"
]

LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'de': 'Deutsch',
    'fr': 'Français',
    'uk': 'Українська'
}

SITE_URL = 'https://fellowtraveler.club'
BASIC_TRAVELER = 'Teddy'
ALL_TRAVELERS = ['Teddy']

def valid_url_extension(url, extension_list=VALID_IMAGE_EXTENSIONS):
    '''
    Validating image extension
    A simple method to make sure the URL the user has supplied has
    an image-like file at the tail of the path
    '''
    return any([url.endswith(e) for e in extension_list])


def valid_url_mimetype(url, mimetype_list=VALID_IMAGE_MIMETYPES):
    '''
    Validating image mimetype
    http://stackoverflow.com/a/10543969/396300
    '''
    mimetype, encoding = mimetypes.guess_type(url)
    if mimetype:
        return any([mimetype.startswith(m) for m in mimetype_list])
    else:
        return False


def image_exists(url):
    '''
    Validating that the image exists on the server
    '''
    try:
        r = requests.get(url)
    except:
        return False
    return r.status_code == 200


def photo_check_save(photo_file, OURTRAVELER):
    '''
    Check image validity using valid_url_extension() and valid_url_mimetype() and return new file name or flash an error
    '''
    photo_filename = secure_filename(photo_file.filename)
    if valid_url_extension(photo_filename) and valid_url_mimetype(photo_filename):
        file_name_wo_extension = 'fellowtravelerclub-{}'.format(OURTRAVELER)
        file_extension = os.path.splitext(photo_filename)[1]
        current_datetime = datetime.datetime.now().strftime("%d%m%y%H%M%S")
        random_int = randint(100, 999)
        path4db = file_name_wo_extension + '-' + current_datetime + str(random_int) + file_extension
        return path4db
    else:
        flash(lazy_gettext('File {} has invalid image extension (not ".jpg", ".jpeg", ".png", ".gif" or ".bmp") or invalid image format').format(photo_filename),
            'addlocation')
        return 'error'


def get_location_history(traveller, PHOTO_DIR):
    '''
    Return locations history for a given traveller (will be substituted with Twitter's timeline)
    '''
    client = MongoClient()
    db = client.TeddyGo
    teddys_locations = db[traveller].find().sort([('_id', -1)])

    # Prepare a list of info blocks about traveller's locations and data to create a map
    locations_history = []
    mymarkers = []
    start_lat = None
    start_long = None
    marker_number = db[traveller].find().count()
    for location in teddys_locations:
        author = location['author']
        comment = location['comment']
        photos = location['photos']

        location_data = {
            'location_number': marker_number,
            'author': author,
            'location': location['formatted_address'],
            'time': '{} {}'.format(location['_id'].generation_time.date(), location['_id'].generation_time.time()),
            'comment': comment,
            'photos': photos
        }

        locations_history.append(location_data)

        if start_lat == None:
            start_lat = location['latitude']
            start_long = location['longitude']
        infobox = '{}<br>'.format(location_data['time'])
        if len(photos) > 0:
            infobox += '<img src="{}/{}/{}" style="max-height: 70px; max-width:120px"/>'.format(PHOTO_DIR, traveller, photos[0])
        infobox += '<br>'
        infobox += gettext('By <b>{}</b>').format(author)
        if comment != '':
            infobox += '<br>'
            infobox += '<i>{}</i>'.format(comment)

        mymarkers.append(
            {
                'icon': 'http://chart.apis.google.com/chart?chst=d_map_pin_letter&chld={}|AFC846|304300'.format(marker_number),
                'lat': location['latitude'],
                'lng': location['longitude'],
                'infobox': infobox
            }
        )
        marker_number -= 1
    return {'locations_history': locations_history, 'start_lat': start_lat, 'start_long': start_long, 'mymarkers': mymarkers}


def summarize_journey(traveller):
    '''
        For a given traveller (for eg., "Teddy") function retrieves documents from our mongoDB (TeddyGo >> Teddy)
        and summarizes:
        1) place of origin;
        2) journey start date/time;
        3) quantity of places traveller was "checked in";
        4) list of locations coordinates to (later) calculate approximate distance between locations;
        5) quantity of countries visited;
        6) list of countries visited
        Data are saved to document TeddyGo >> travellers >> <Traveller>
    '''
    countries_name_codes = [{"Code": "AF", "Name": lazy_gettext("Afghanistan")},
                            {"Code": "AX", "Name": lazy_gettext("\u00c5land Islands")},
                            {"Code": "AL", "Name": lazy_gettext("Albania")},
                            {"Code": "DZ", "Name": lazy_gettext("Algeria")},
                            {"Code": "AS", "Name": lazy_gettext("American Samoa")},
                            {"Code": "AD", "Name": lazy_gettext("Andorra")},
                            {"Code": "AO", "Name": lazy_gettext("Angola")},
                            {"Code": "AI", "Name": lazy_gettext("Anguilla")},
                            {"Code": "AQ", "Name": lazy_gettext("Antarctica")},
                            {"Code": "AG", "Name": lazy_gettext("Antigua and Barbuda")},
                            {"Code": "AR", "Name": lazy_gettext("Argentina")},
                            {"Code": "AM", "Name": lazy_gettext("Armenia")},
                            {"Code": "AW", "Name": lazy_gettext("Aruba")},
                            {"Code": "AU", "Name": lazy_gettext("Australia")},
                            {"Code": "AT", "Name": lazy_gettext("Austria")},
                            {"Code": "AZ", "Name": lazy_gettext("Azerbaijan")},
                            {"Code": "BS", "Name": lazy_gettext("Bahamas")},
                            {"Code": "BH", "Name": lazy_gettext("Bahrain")},
                            {"Code": "BD", "Name": lazy_gettext("Bangladesh")},
                            {"Code": "BB", "Name": lazy_gettext("Barbados")},
                            {"Code": "BY", "Name": lazy_gettext("Belarus")},
                            {"Code": "BE", "Name": lazy_gettext("Belgium")},
                            {"Code": "BZ", "Name": lazy_gettext("Belize")},
                            {"Code": "BJ", "Name": lazy_gettext("Benin")},
                            {"Code": "BM", "Name": lazy_gettext("Bermuda")},
                            {"Code": "BT", "Name": lazy_gettext("Bhutan")},
                            {"Code": "BO", "Name": lazy_gettext("Bolivia, Plurinational State of")},
                            {"Code": "BQ", "Name": lazy_gettext("Bonaire, Sint Eustatius and Saba")},
                            {"Code": "BA", "Name": lazy_gettext("Bosnia and Herzegovina")},
                            {"Code": "BW", "Name": lazy_gettext("Botswana")},
                            {"Code": "BV", "Name": lazy_gettext("Bouvet Island")},
                            {"Code": "BR", "Name": lazy_gettext("Brazil")},
                            {"Code": "IO", "Name": lazy_gettext("British Indian Ocean Territory")},
                            {"Code": "BN", "Name": lazy_gettext("Brunei Darussalam")},
                            {"Code": "BG", "Name": lazy_gettext("Bulgaria")},
                            {"Code": "BF", "Name": lazy_gettext("Burkina Faso")},
                            {"Code": "BI", "Name": lazy_gettext("Burundi")},
                            {"Code": "KH", "Name": lazy_gettext("Cambodia")},
                            {"Code": "CM", "Name": lazy_gettext("Cameroon")},
                            {"Code": "CA", "Name": lazy_gettext("Canada")},
                            {"Code": "CV", "Name": lazy_gettext("Cape Verde")},
                            {"Code": "KY", "Name": lazy_gettext("Cayman Islands")},
                            {"Code": "CF", "Name": lazy_gettext("Central African Republic")},
                            {"Code": "TD", "Name": lazy_gettext("Chad")},
                            {"Code": "CL", "Name": lazy_gettext("Chile")},
                            {"Code": "CN", "Name": lazy_gettext("China")},
                            {"Code": "CX", "Name": lazy_gettext("Christmas Island")},
                            {"Code": "CC", "Name": lazy_gettext("Cocos (Keeling) Islands")},
                            {"Code": "CO", "Name": lazy_gettext("Colombia")},
                            {"Code": "KM", "Name": lazy_gettext("Comoros")},
                            {"Code": "CG", "Name": lazy_gettext("Congo")},
                            {"Code": "CD", "Name": lazy_gettext("Congo, the Democratic Republic of the")},
                            {"Code": "CK", "Name": lazy_gettext("Cook Islands")},
                            {"Code": "CR", "Name": lazy_gettext("Costa Rica")},
                            {"Code": "CI", "Name": lazy_gettext("C\u00f4te d'Ivoire")},
                            {"Code": "HR", "Name": lazy_gettext("Croatia")},
                            {"Code": "CU", "Name": lazy_gettext("Cuba")},
                            {"Code": "CW", "Name": lazy_gettext("Cura\u00e7ao")},
                            {"Code": "CY", "Name": lazy_gettext("Cyprus")},
                            {"Code": "CZ", "Name": lazy_gettext("Czech Republic")},
                            {"Code": "DK", "Name": lazy_gettext("Denmark")},
                            {"Code": "DJ", "Name": lazy_gettext("Djibouti")},
                            {"Code": "DM", "Name": lazy_gettext("Dominica")},
                            {"Code": "DO", "Name": lazy_gettext("Dominican Republic")},
                            {"Code": "EC", "Name": lazy_gettext("Ecuador")},
                            {"Code": "EG", "Name": lazy_gettext("Egypt")},
                            {"Code": "SV", "Name": lazy_gettext("El Salvador")},
                            {"Code": "GQ", "Name": lazy_gettext("Equatorial Guinea")},
                            {"Code": "ER", "Name": lazy_gettext("Eritrea")},
                            {"Code": "EE", "Name": lazy_gettext("Estonia")},
                            {"Code": "ET", "Name": lazy_gettext("Ethiopia")},
                            {"Code": "FK", "Name": lazy_gettext("Falkland Islands (Malvinas)")},
                            {"Code": "FO", "Name": lazy_gettext("Faroe Islands")},
                            {"Code": "FJ", "Name": lazy_gettext("Fiji")},
                            {"Code": "FI", "Name": lazy_gettext("Finland")},
                            {"Code": "FR", "Name": lazy_gettext("France")},
                            {"Code": "GF", "Name": lazy_gettext("French Guiana")},
                            {"Code": "PF", "Name": lazy_gettext("French Polynesia")},
                            {"Code": "TF", "Name": lazy_gettext("French Southern Territories")},
                            {"Code": "GA", "Name": lazy_gettext("Gabon")},
                            {"Code": "GM", "Name": lazy_gettext("Gambia")},
                            {"Code": "GE", "Name": lazy_gettext("Georgia")},
                            {"Code": "DE", "Name": lazy_gettext("Germany")},
                            {"Code": "GH", "Name": lazy_gettext("Ghana")},
                            {"Code": "GI", "Name": lazy_gettext("Gibraltar")},
                            {"Code": "GR", "Name": lazy_gettext("Greece")},
                            {"Code": "GL", "Name": lazy_gettext("Greenland")},
                            {"Code": "GD", "Name": lazy_gettext("Grenada")},
                            {"Code": "GP", "Name": lazy_gettext("Guadeloupe")},
                            {"Code": "GU", "Name": lazy_gettext("Guam")},
                            {"Code": "GT", "Name": lazy_gettext("Guatemala")},
                            {"Code": "GG", "Name": lazy_gettext("Guernsey")},
                            {"Code": "GN", "Name": lazy_gettext("Guinea")},
                            {"Code": "GW", "Name": lazy_gettext("Guinea-Bissau")},
                            {"Code": "GY", "Name": lazy_gettext("Guyana")},
                            {"Code": "HT", "Name": lazy_gettext("Haiti")},
                            {"Code": "HM", "Name": lazy_gettext("Heard Island and McDonald Islands")},
                            {"Code": "VA", "Name": lazy_gettext("Holy See (Vatican City State)")},
                            {"Code": "HN", "Name": lazy_gettext("Honduras")},
                            {"Code": "HK", "Name": lazy_gettext("Hong Kong")},
                            {"Code": "HU", "Name": lazy_gettext("Hungary")},
                            {"Code": "IS", "Name": lazy_gettext("Iceland")},
                            {"Code": "IN", "Name": lazy_gettext("India")},
                            {"Code": "ID", "Name": lazy_gettext("Indonesia")},
                            {"Code": "IR", "Name": lazy_gettext("Iran, Islamic Republic of")},
                            {"Code": "IQ", "Name": lazy_gettext("Iraq")},
                            {"Code": "IE", "Name": lazy_gettext("Ireland")},
                            {"Code": "IM", "Name": lazy_gettext("Isle of Man")},
                            {"Code": "IL", "Name": lazy_gettext("Israel")},
                            {"Code": "IT", "Name": lazy_gettext("Italy")},
                            {"Code": "JM", "Name": lazy_gettext("Jamaica")},
                            {"Code": "JP", "Name": lazy_gettext("Japan")},
                            {"Code": "JE", "Name": lazy_gettext("Jersey")},
                            {"Code": "JO", "Name": lazy_gettext("Jordan")},
                            {"Code": "KZ", "Name": lazy_gettext("Kazakhstan")},
                            {"Code": "KE", "Name": lazy_gettext("Kenya")},
                            {"Code": "KI", "Name": lazy_gettext("Kiribati")},
                            {"Code": "KP", "Name": lazy_gettext("Korea, Democratic People's Republic of")},
                            {"Code": "KR", "Name": lazy_gettext("Korea, Republic of")},
                            {"Code": "KW", "Name": lazy_gettext("Kuwait")},
                            {"Code": "KG", "Name": lazy_gettext("Kyrgyzstan")},
                            {"Code": "LA", "Name": lazy_gettext("Lao People's Democratic Republic")},
                            {"Code": "LV", "Name": lazy_gettext("Latvia")},
                            {"Code": "LB", "Name": lazy_gettext("Lebanon")},
                            {"Code": "LS", "Name": lazy_gettext("Lesotho")},
                            {"Code": "LR", "Name": lazy_gettext("Liberia")},
                            {"Code": "LY", "Name": lazy_gettext("Libya")},
                            {"Code": "LI", "Name": lazy_gettext("Liechtenstein")},
                            {"Code": "LT", "Name": lazy_gettext("Lithuania")},
                            {"Code": "LU", "Name": lazy_gettext("Luxembourg")},
                            {"Code": "MO", "Name": lazy_gettext("Macao")},
                            {"Code": "MK", "Name": lazy_gettext("Macedonia, the Former Yugoslav Republic of")},
                            {"Code": "MG", "Name": lazy_gettext("Madagascar")},
                            {"Code": "MW", "Name": lazy_gettext("Malawi")},
                            {"Code": "MY", "Name": lazy_gettext("Malaysia")},
                            {"Code": "MV", "Name": lazy_gettext("Maldives")},
                            {"Code": "ML", "Name": lazy_gettext("Mali")}, {"Code": "MT", "Name": lazy_gettext("Malta")},
                            {"Code": "MH", "Name": lazy_gettext("Marshall Islands")},
                            {"Code": "MQ", "Name": lazy_gettext("Martinique")},
                            {"Code": "MR", "Name": lazy_gettext("Mauritania")},
                            {"Code": "MU", "Name": lazy_gettext("Mauritius")},
                            {"Code": "YT", "Name": lazy_gettext("Mayotte")},
                            {"Code": "MX", "Name": lazy_gettext("Mexico")},
                            {"Code": "FM", "Name": lazy_gettext("Micronesia, Federated States of")},
                            {"Code": "MD", "Name": lazy_gettext("Moldova, Republic of")},
                            {"Code": "MC", "Name": lazy_gettext("Monaco")},
                            {"Code": "MN", "Name": lazy_gettext("Mongolia")},
                            {"Code": "ME", "Name": lazy_gettext("Montenegro")},
                            {"Code": "MS", "Name": lazy_gettext("Montserrat")},
                            {"Code": "MA", "Name": lazy_gettext("Morocco")},
                            {"Code": "MZ", "Name": lazy_gettext("Mozambique")},
                            {"Code": "MM", "Name": lazy_gettext("Myanmar")},
                            {"Code": "NA", "Name": lazy_gettext("Namibia")},
                            {"Code": "NR", "Name": lazy_gettext("Nauru")},
                            {"Code": "NP", "Name": lazy_gettext("Nepal")},
                            {"Code": "NL", "Name": lazy_gettext("Netherlands")},
                            {"Code": "NC", "Name": lazy_gettext("New Caledonia")},
                            {"Code": "NZ", "Name": lazy_gettext("New Zealand")},
                            {"Code": "NI", "Name": lazy_gettext("Nicaragua")},
                            {"Code": "NE", "Name": lazy_gettext("Niger")},
                            {"Code": "NG", "Name": lazy_gettext("Nigeria")},
                            {"Code": "NU", "Name": lazy_gettext("Niue")},
                            {"Code": "NF", "Name": lazy_gettext("Norfolk Island")},
                            {"Code": "MP", "Name": lazy_gettext("Northern Mariana Islands")},
                            {"Code": "NO", "Name": lazy_gettext("Norway")},
                            {"Code": "OM", "Name": lazy_gettext("Oman")},
                            {"Code": "PK", "Name": lazy_gettext("Pakistan")},
                            {"Code": "PW", "Name": lazy_gettext("Palau")},
                            {"Code": "PS", "Name": lazy_gettext("Palestine, State of")},
                            {"Code": "PA", "Name": lazy_gettext("Panama")},
                            {"Code": "PG", "Name": lazy_gettext("Papua New Guinea")},
                            {"Code": "PY", "Name": lazy_gettext("Paraguay")},
                            {"Code": "PE", "Name": lazy_gettext("Peru")},
                            {"Code": "PH", "Name": lazy_gettext("Philippines")},
                            {"Code": "PN", "Name": lazy_gettext("Pitcairn")},
                            {"Code": "PL", "Name": lazy_gettext("Poland")},
                            {"Code": "PT", "Name": lazy_gettext("Portugal")},
                            {"Code": "PR", "Name": lazy_gettext("Puerto Rico")},
                            {"Code": "QA", "Name": lazy_gettext("Qatar")},
                            {"Code": "RE", "Name": lazy_gettext("R\u00e9union")},
                            {"Code": "RO", "Name": lazy_gettext("Romania")},
                            {"Code": "RU", "Name": lazy_gettext("Russian Federation")},
                            {"Code": "RW", "Name": lazy_gettext("Rwanda")},
                            {"Code": "BL", "Name": lazy_gettext("Saint Barth\u00e9lemy")},
                            {"Code": "SH", "Name": lazy_gettext("Saint Helena, Ascension and Tristan da Cunha")},
                            {"Code": "KN", "Name": lazy_gettext("Saint Kitts and Nevis")},
                            {"Code": "LC", "Name": lazy_gettext("Saint Lucia")},
                            {"Code": "MF", "Name": lazy_gettext("Saint Martin (French part)")},
                            {"Code": "PM", "Name": lazy_gettext("Saint Pierre and Miquelon")},
                            {"Code": "VC", "Name": lazy_gettext("Saint Vincent and the Grenadines")},
                            {"Code": "WS", "Name": lazy_gettext("Samoa")},
                            {"Code": "SM", "Name": lazy_gettext("San Marino")},
                            {"Code": "ST", "Name": lazy_gettext("Sao Tome and Principe")},
                            {"Code": "SA", "Name": lazy_gettext("Saudi Arabia")},
                            {"Code": "SN", "Name": lazy_gettext("Senegal")},
                            {"Code": "RS", "Name": lazy_gettext("Serbia")},
                            {"Code": "SC", "Name": lazy_gettext("Seychelles")},
                            {"Code": "SL", "Name": lazy_gettext("Sierra Leone")},
                            {"Code": "SG", "Name": lazy_gettext("Singapore")},
                            {"Code": "SX", "Name": lazy_gettext("Sint Maarten (Dutch part)")},
                            {"Code": "SK", "Name": lazy_gettext("Slovakia")},
                            {"Code": "SI", "Name": lazy_gettext("Slovenia")},
                            {"Code": "SB", "Name": lazy_gettext("Solomon Islands")},
                            {"Code": "SO", "Name": lazy_gettext("Somalia")},
                            {"Code": "ZA", "Name": lazy_gettext("South Africa")},
                            {"Code": "GS", "Name": lazy_gettext("South Georgia and the South Sandwich Islands")},
                            {"Code": "SS", "Name": lazy_gettext("South Sudan")},
                            {"Code": "ES", "Name": lazy_gettext("Spain")},
                            {"Code": "LK", "Name": lazy_gettext("Sri Lanka")},
                            {"Code": "SD", "Name": lazy_gettext("Sudan")},
                            {"Code": "SR", "Name": lazy_gettext("Suriname")},
                            {"Code": "SJ", "Name": lazy_gettext("Svalbard and Jan Mayen")},
                            {"Code": "SZ", "Name": lazy_gettext("Swaziland")},
                            {"Code": "SE", "Name": lazy_gettext("Sweden")},
                            {"Code": "CH", "Name": lazy_gettext("Switzerland")},
                            {"Code": "SY", "Name": lazy_gettext("Syrian Arab Republic")},
                            {"Code": "TW", "Name": lazy_gettext("Taiwan, Province of China")},
                            {"Code": "TJ", "Name": lazy_gettext("Tajikistan")},
                            {"Code": "TZ", "Name": lazy_gettext("Tanzania, United Republic of")},
                            {"Code": "TH", "Name": lazy_gettext("Thailand")},
                            {"Code": "TL", "Name": lazy_gettext("Timor-Leste")},
                            {"Code": "TG", "Name": lazy_gettext("Togo")},
                            {"Code": "TK", "Name": lazy_gettext("Tokelau")},
                            {"Code": "TO", "Name": lazy_gettext("Tonga")},
                            {"Code": "TT", "Name": lazy_gettext("Trinidad and Tobago")},
                            {"Code": "TN", "Name": lazy_gettext("Tunisia")},
                            {"Code": "TR", "Name": lazy_gettext("Turkey")},
                            {"Code": "TM", "Name": lazy_gettext("Turkmenistan")},
                            {"Code": "TC", "Name": lazy_gettext("Turks and Caicos Islands")},
                            {"Code": "TV", "Name": lazy_gettext("Tuvalu")},
                            {"Code": "UG", "Name": lazy_gettext("Uganda")},
                            {"Code": "UA", "Name": lazy_gettext("Ukraine")},
                            {"Code": "AE", "Name": lazy_gettext("United Arab Emirates")},
                            {"Code": "GB", "Name": lazy_gettext("United Kingdom")},
                            {"Code": "US", "Name": lazy_gettext("United States")},
                            {"Code": "UM", "Name": lazy_gettext("United States Minor Outlying Islands")},
                            {"Code": "UY", "Name": lazy_gettext("Uruguay")},
                            {"Code": "UZ", "Name": lazy_gettext("Uzbekistan")},
                            {"Code": "VU", "Name": lazy_gettext("Vanuatu")},
                            {"Code": "VE", "Name": lazy_gettext("Venezuela, Bolivarian Republic of")},
                            {"Code": "VN", "Name": lazy_gettext("Viet Nam")},
                            {"Code": "VG", "Name": lazy_gettext("Virgin Islands, British")},
                            {"Code": "VI", "Name": lazy_gettext("Virgin Islands, U.S.")},
                            {"Code": "WF", "Name": lazy_gettext("Wallis and Futuna")},
                            {"Code": "EH", "Name": lazy_gettext("Western Sahara")},
                            {"Code": "YE", "Name": lazy_gettext("Yemen")},
                            {"Code": "ZM", "Name": lazy_gettext("Zambia")},
                            {"Code": "ZW", "Name": lazy_gettext("Zimbabwe")}]

    client = MongoClient()
    db = client.TeddyGo
    locations = db[traveller].find()

    origin = locations[0]['formatted_address']  # 1
    start_date = '{} {}'.format(locations[0]['_id'].generation_time.date(), locations[0]['_id'].generation_time.time()) # 2
    start_date_service = locations[0]['_id'].generation_time
    total_locations = 0 #3
    locations_lat_long = []  # 4
    total_countries = 0 #5
    countries_visited = [] #6

    for location in locations:
        total_locations += 1

        country_code = location['country']
        contry_name = None
        for country in countries_name_codes:
            if country['Code'] == country_code:
                contry_name = country['Name']
        if contry_name not in countries_visited:
            total_countries += 1
            countries_visited.append(contry_name)

        lat = location['latitude']
        lng = location['longitude']
        locations_lat_long.append({'latitude': lat, 'longitude': lng})

        datatoupdate = {
            'origin': origin,
            'start_date': start_date,
            'start_date_service': start_date_service,
            'total_locations': total_locations,
            'locations_lat_long': locations_lat_long,
            'total_countries': total_countries,
            'countries_visited': countries_visited
        }

    # Update total distance and distance from home
    new_distance_from_home = distance_from_home(traveller)
    if new_distance_from_home:
        datatoupdate['distance_from_home'] = new_distance_from_home
    new_total_distance = last_segment_distance_append(traveller)
    if new_total_distance:
        datatoupdate['total_distance'] = new_total_distance

    try:
        db.travellers.update_one({'name': traveller}, {'$set': datatoupdate})
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

    return {'status': 'success', 'message': datatoupdate}


def get_journey_summary(traveller):
    '''
    Retrieves journey summary for a given traveller
    '''
    try:
        client = MongoClient()
        db = client.TeddyGo

        # Message: I've checked in ... places in ... country[ies] (country1 [, country2 etc]) and have been traveling for ... days so far
        traveller_summary = db.travellers.find_one({'name': traveller})
        if traveller_summary:
            total_locations = traveller_summary['total_locations']
            total_countries = traveller_summary['total_countries']
            countries_visited = traveller_summary['countries_visited']
            countries = ', '.join(countries_visited)
            journey_duration = time_passed(traveller)
            total_distance = round(traveller_summary['total_distance'] / 1000, 1)
            distance_from_home = round(traveller_summary['distance_from_home'] / 1000, 1)
            if total_countries == 1:
                countries_form = gettext('country')
            else:
                countries_form = gettext('countries')
            if journey_duration == 1:
                day_or_days = gettext('day')
            else:
                day_or_days = gettext('days')

            speech = gettext('So far I\'ve checked in <b>{}</b> places located in <b>{}</b> {} ({}) and have been traveling for <b>{}</b> {}.\n\nI covered about <b>{}</b> km it total and currently I\'m nearly <b>{}</b> km from home').format(
                total_locations, total_countries, countries_form, countries, journey_duration, day_or_days, total_distance,
                distance_from_home)
            return {'speech': speech, 'total_locations': total_locations}
        else:
            return {'speech': '', 'total_locations': 0}
    except Exception as e:
        print('get_journey_summary() exception: {}'.format(e))
        return False


def time_passed(traveller):
    '''
        Function calculates time elapsed from origin date/time for a given traveller
    '''
    client = MongoClient()
    db = client.TeddyGo
    traveller_resume = db.travellers.find_one({'name': traveller})
    start_date_service = traveller_resume['start_date_service']
    current_datetime = datetime.datetime.now()
    difference = (current_datetime - start_date_service).days
    return difference


def get_distance(origin, destination):
    '''
        Uusing Distance Matrix API calculates and returns approximate distance (m) between origin and destination
        (lists of latitude/longitude)
        https://developers.google.com/maps/documentation/distance-matrix/intro
    '''
    try:
        query = 'https://maps.googleapis.com/maps/api/distancematrix/json?units=metric&origins={},{}&destinations={},{}&key={}'.format(
            origin[0], origin[1], destination[0], destination[1], GOOGLE_MAPS_API_KEY)
        r = requests.get(query).json()
        distance = r.get('rows', 0)[0].get('elements', 0)[0].get('distance', 0).get('value', 0)
        return distance
    except Exception as e:
        print('get_distance() exception: {}'.format(e))
        return False


def journey_distance_recalculate(traveller):
    '''
        Calculates using Distance Matrix API approximate distance (km) between all locations visited by traveller
        https://developers.google.com/maps/documentation/distance-matrix/intro
        Function may be used in case some location is deleted from DB
        Otherwise after adding every location function journey_distance() calculates distance between the last
        2 locations and updates total distance value stored in DB (TeddyGo >> travellers >> <Traveller> document >>
        'total_distance' field
    '''
    try:
        client = MongoClient()
        db = client.TeddyGo
        locations = db[traveller].find()

        locations_lat_lng = []
        lat_lng_pair = []
        journey_distance = 0 # meters, integer

        for location in locations:
            lat_lng_pair.append(location['latitude'])
            lat_lng_pair.append(location['longitude'])
            locations_lat_lng.append(lat_lng_pair)
            lat_lng_pair = []

        for x in range(1, len(locations_lat_lng)):
            origin = locations_lat_lng[x-1]
            destination = locations_lat_lng[x]
            segment_distance = get_distance(origin, destination)
            if not segment_distance:
                segment_distance = 0

            journey_distance += segment_distance

        db.travellers.update_one({'name': traveller}, {'$set': {'total_distance': journey_distance}})
        return True
    except Exception as e:
        print('journey_distance_recalculate() exception: {}'.format(e))
        return False


def distance_from_home(traveller):
    '''
        Using Distance Matrix API calculates and returns approximate distance (meters) between the 1st and the last locations
        (this distance may be less than the sum of distances between all locations if traveller is 'returning home' for eg.)
        https://developers.google.com/maps/documentation/distance-matrix/intro
    '''
    try:
        distance_from_home = 0

        client = MongoClient()
        db = client.TeddyGo
        if db[traveller].find().count() >= 2:
            origin_location = db[traveller].find().limit(1)[0]
            last_location = db[traveller].find().limit(1).sort([('_id', -1)])[0]

            origin = [origin_location['latitude'], origin_location['longitude']]
            destination = [last_location['latitude'], last_location['longitude']]

            distance_from_home = get_distance(origin, destination)
            if not distance_from_home:
                distance_from_home = 0
        return distance_from_home
    except Exception as e:
        print('distance_from_home() exception: {}'.format(e))
        return False


def last_segment_distance_append(traveller):
    '''
        Using Distance Matrix API calculates approximate distance (meters) between the last 2 locations and
        adds it to the value of 'total_distance' field in db TeddyGo >> travellers >> <Traveller> document
        The function is used after adding every location
        https://developers.google.com/maps/documentation/distance-matrix/intro
    '''
    try:
        new_distance = 0

        client = MongoClient()
        db = client.TeddyGo
        if db[traveller].find().count() >= 2:
            locations = db[traveller].find().sort([('_id', -1)]).limit(2)
            curr_location = locations[0]
            prev_location = locations[1]

            # Total distance before current location was added ('total_distance' field in <Traveller> doc)
            last_distance = db.travellers.find_one({'name': traveller})['total_distance']

            origin = [prev_location['latitude'], prev_location['longitude']]
            destination = [curr_location['latitude'], curr_location['longitude']]

            last_segment_distance = get_distance(origin, destination)

            if not last_segment_distance:
                last_segment_distance = 0

            new_distance = last_distance + last_segment_distance
        return new_distance
    except Exception as e:
        print('last_segment_distance_append() exception: {}'.format(e))
        return False


def code_regenerate(traveller):
    '''
        After adding a new location secret code is being regenerated so that if user1 passes the toy
        to user2, user1 should not be able to add new locations or share secret code
        New code is saved to traveller's summary document in DB (TeddyGo >> travellers >> <TravellerName>), secret_code
    '''
    new_code = ''
    for x in range(4):
        new_code += str(randint(0,9))
    try:
        client = MongoClient()
        db = client.TeddyGo
        db.travellers.update_one({'name': traveller}, {'$set': {'secret_code': sha256_crypt.encrypt(new_code)}})
    except Exception as e:
        print('code_regenerate() exception when updating secret code in DB: {}'.format(e))
        return False

    # Logging
    print()
    print('New secret code for {}: {}'.format(traveller, new_code))
    return new_code


def get_locale():
    user_language = request.cookies.get('UserPreferredLanguage')
    if user_language != None:
        return user_language
    else:
        return request.accept_languages.best_match(LANGUAGES.keys())


def get_traveler():
    '''
        Retrieves traveler watched by user from session
        By default returns BASIC_TRAVELER
    '''
    OURTRAVELER = session.get('which_traveler', BASIC_TRAVELER)
    if OURTRAVELER not in ALL_TRAVELERS:
        OURTRAVELER = BASIC_TRAVELER
    return OURTRAVELER