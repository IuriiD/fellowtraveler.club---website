# -*- coding: utf-8 -*-

import os
import mimetypes
import requests
from flask import request, flash, url_for, redirect
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import datetime
#import googlemaps

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

# Validating image extension
def valid_url_extension(url, extension_list=VALID_IMAGE_EXTENSIONS):
    '''
    A simple method to make sure the URL the user has supplied has
    an image-like file at the tail of the path
    '''
    return any([url.endswith(e) for e in extension_list])

# Validating image mimetype
def valid_url_mimetype(url, mimetype_list=VALID_IMAGE_MIMETYPES):
    # http://stackoverflow.com/a/10543969/396300
    mimetype, encoding = mimetypes.guess_type(url)
    print('mimetype: {}'.format(mimetype))
    if mimetype:
        return any([mimetype.startswith(m) for m in mimetype_list])
    else:
        return False

# Validating that the image exists on the server
def image_exists(url):
    try:
        r = requests.get(url)
    except:
        return False
    return r.status_code == 200

# Check image validity using valid_url_extension() and valid_url_mimetype() and return new file name or flash an error
def photo_check_save(photo_file):
    print('photo_file: {}'.format(photo_file))
    photo_filename = secure_filename(photo_file.filename)
    if valid_url_extension(photo_filename) and valid_url_mimetype(photo_filename):
        file_name_wo_extension = os.path.splitext(photo_filename)[0]
        file_extension = os.path.splitext(photo_filename)[1]
        current_datetime = datetime.datetime.now().strftime("%d%m%y%H%M%S")
        path = 'uploads/' + file_name_wo_extension + '-' + current_datetime + file_extension
        return path
    else:
        flash(
            'File {} has invalid image extension (not ".jpg", ".jpeg", ".png", ".gif" or ".bmp") or invalid image format'.format(photo_filename),
            'addlocation')
        return 'error'

# Return locations history for a given traveller (will be substituted with Twitter's timeline)
def get_location_history(traveller):
    client = MongoClient()
    db = client.TeddyGo
    teddys_locations = db[traveller].find().sort([('_id', -1)])
    # Prepare a list of info blocks about traveller's locations and data to create a map
    locations_history = []
    mymarkers = []
    start_lat = None
    start_long = None
    for location in teddys_locations:
        author = location['author']
        comment = location['comment']
        photos = location['photos']

        location_data = {
            'author': author,
            'location': location['formatted_address'],
            'time': '{} {}'.format(location['_id'].generation_time.date(), location['_id'].generation_time.time()),
            'comment': comment,
            'photos': photos
        }
        #print("location_data: {}".format(location_data))
        locations_history.append(location_data)

        if start_lat == None:
            start_lat = location['latitude']
            start_long = location['longitude']
        infobox = '{}<br>'.format(location_data['time'])
        if len(photos) > 0:
            infobox += '<img src="static/{}" style="max-height: 70px; max-width:120px"/>'.format(photos[0])
        infobox += '<br>'
        infobox += 'By <b>{}</b>'.format(author)
        if comment != '':
            infobox += '<br>'
            infobox += '<i>{}</i>'.format(comment)

        mymarkers.append(
            {
                'icon': 'http://maps.google.com/mapfiles/ms/icons/green-dot.png',
                'lat': location['latitude'],
                'lng': location['longitude'],
                'infobox': infobox
            }
        )
    return {'locations_history': locations_history, 'start_lat': start_lat, 'start_long': start_long, 'mymarkers': mymarkers}

def make_speech(ourspeech, oursource, outputcontext):
    '''
        Composes response for different platforms
    '''
    basic_txt_message = ourspeech["speech"]
    if "rich_messages" in ourspeech:
        rich_messages = ourspeech["rich_messages"]
    else:
        rich_messages = []

    res = {
        'speech': basic_txt_message,
        'displayText': basic_txt_message,
        'source': oursource,

        'messages': [message for message in rich_messages],
        'contextOut': outputcontext
    }
    return res

def last_location_shown(req):
    '''
        From JSON-response got from webhook retrieves context 'location_shown' and value of parameter 'locationN'
        (last shown location's number; -1 if we only start to display locations
    '''
    contexts = req.get('result').get('contexts')
    last_location = -1
    for context in contexts:
        if context['name'] == 'location_shown':
            last_location = context.get('parameters').get('locationN')
    return int(last_location)

def show_next_location(req, locations_history, last_location_shown):
    total_locations = len(locations_history)
    contexts = req.get('result').get('contexts')
    if (last_location_shown + 1) > total_locations:
        # all locations have been shown
        payload = {
            "speech": "That\'s all my travel so far",
            "rich_messages": [
                {
                    "platform": "telegram",
                    "type": 0,
                    "speech": "That\'s all my travel so far"
                }
            ]
        }
        for context in contexts:
            if context['name'] == 'location_shown':
                context['parameters']['locationN'] = -1
    else:
        location_to_show = locations_history[last_location_shown + 1]
        author = location_to_show['author']
        location = location_to_show['formatted_address'].split()[0]
        time = location_to_show['time']
        comment = location_to_show['comment']
        photos = location_to_show['photos']
        title = "{} - {}".format(time, location)
        if len(photos) > 0:
            imageUrl = "https://iuriid.github.io/img/pb-3.jpg"
        else:
            imageUrl = ""
        if len(comment) > 0:
            subtitle = "{} wrote: {}".format(author, comment)
        else:
            subtitle = ""
        if (last_location_shown + 1) < total_locations:
            buttons = [
                {
                    "postback": "Show next location",
                    "text": "Show next place"
                }
            ]
        else:
            buttons = []

        for context in contexts:
            if context['name'] == 'location_shown':
                context['parameters']['locationN'] = last_location_shown + 1

        payload = {
            "speech": "{}\n{}\n{}".format(title, subtitle, imageUrl),
            "rich_messages": [
                {
                    "platform": "telegram",
                    "type": 1,
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": imageUrl,
                    "buttons": buttons
                }
            ]
        }

    response = {"status": "ok", "payload": payload, 'updated_context': contexts}
    return response

def show_location(traveller, req):
    '''
        Function gets traveller name (for eg., 'Teddy') and request JSON from webhook ('teddygo_show_timeline')
        Displays the next location for traveller depending on locations previously shown (which is saved in req's
        context named 'location_shown' >> parameter 'locationN'
        1) If it's the 1st location - returns an 'intro' message, location + 'Show next location' button
        2) If it's not the 1st, but not the last location - shows location and 'Show next location' button
        3) If it's the last location to show - no 'Show next location' button and a 'summary' message
    '''
    # Get a list of all traveller's locations
    allhistory = get_location_history(traveller)['locations_history'][::-1]

    # Get the number of last shown location from req's contexts
    contexts = req.get('result').get('contexts')
    for context in contexts:
        if context['name'] == 'location_shown':
            last_location = int(context.get('parameters').get('locationN', -1))
            if last_location == -1 or (last_location + 1) < len(allhistory):
                context['parameters']['locationN'] = int(last_location) + 1
            else:
                context['parameters']['locationN'] = -1
    #print("Locations N: {}".format(len(allhistory)))
    #print("Last location shown #: {}".format(last_location))

    if (last_location + 1) <= len(allhistory):
        location_to_show = allhistory[last_location + 1]
        author = location_to_show['author']
        location = location_to_show['location']
        time = location_to_show['time']
        comment = location_to_show['comment']
        photos = location_to_show['photos']
        title = "{} - {}".format(time, location)
        if len(photos) > 0:
            imageUrl = url_for('static', filename=photos[0])
            #print("imageUrl: {}".format(imageUrl))
        else:
            imageUrl = ""
        if len(comment) > 0:
            subtitle = "{} wrote: {}".format(author, comment)
        else:
            subtitle = ""

    # 1) If it's the 1st location - returns an 'intro' message, location + 'Show next location' button
    if last_location == -1:
        payload = {
            "speech": "{}\n{}\n{}".format(title, subtitle, imageUrl),
            "rich_messages": [
                {
                    "platform": "telegram",
                    "type": 1,
                    "title": "My travel started in {} on {}".format(location, time),
                    "subtitle": subtitle,
                    "imageUrl": imageUrl,
                    "buttons": [
                        {
                            "postback": "timeline",
                            "text": "Show the next place"
                        }
                    ]
                }
            ]
        }
    # 2) If it's not the 1st, but not the last location - shows location and 'Show next location' button
    elif (last_location + 1) < len(allhistory):
        payload = {
            "speech": "{}\n{}\n{}".format(title, subtitle, imageUrl),
            "rich_messages": [
                {
                    "platform": "telegram",
                    "type": 1,
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": imageUrl,
                    "buttons": [
                        {
                            "postback": "timeline",
                            "text": "Show the next place"
                        }
                    ]
                }
            ]
        }
    # 3) If it's the last location to show - no 'Show next location' button and a 'summary' message
    elif (last_location + 1) == len(allhistory):
        payload = {
            "speech": "{}\n{}\n{}".format(title, subtitle, imageUrl),
            "rich_messages": [
                {
                    "platform": "telegram",
                    "type": 1,
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": imageUrl,
                    "buttons": []
                },
                {
                    "platform": "telegram",
                    "type": 0,
                    "speech": "And that's all my travel so far.\nWill you help me to continue it?",
                }
            ]
        }

    response = {"status": "ok", "payload": payload, "updated_context": contexts}
    return response

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
        Data are saved to TeddyGo >> travellers
    '''
    countries_name_codes = [{"Code": "AF", "Name": "Afghanistan"},{"Code": "AX", "Name": "\u00c5land Islands"},{"Code": "AL", "Name": "Albania"},{"Code": "DZ", "Name": "Algeria"},{"Code": "AS", "Name": "American Samoa"},{"Code": "AD", "Name": "Andorra"},{"Code": "AO", "Name": "Angola"},{"Code": "AI", "Name": "Anguilla"},{"Code": "AQ", "Name": "Antarctica"},{"Code": "AG", "Name": "Antigua and Barbuda"},{"Code": "AR", "Name": "Argentina"},{"Code": "AM", "Name": "Armenia"},{"Code": "AW", "Name": "Aruba"},{"Code": "AU", "Name": "Australia"},{"Code": "AT", "Name": "Austria"},{"Code": "AZ", "Name": "Azerbaijan"},{"Code": "BS", "Name": "Bahamas"},{"Code": "BH", "Name": "Bahrain"},{"Code": "BD", "Name": "Bangladesh"},{"Code": "BB", "Name": "Barbados"},{"Code": "BY", "Name": "Belarus"},{"Code": "BE", "Name": "Belgium"},{"Code": "BZ", "Name": "Belize"},{"Code": "BJ", "Name": "Benin"},{"Code": "BM", "Name": "Bermuda"},{"Code": "BT", "Name": "Bhutan"},{"Code": "BO", "Name": "Bolivia, Plurinational State of"},{"Code": "BQ", "Name": "Bonaire, Sint Eustatius and Saba"},{"Code": "BA", "Name": "Bosnia and Herzegovina"},{"Code": "BW", "Name": "Botswana"},{"Code": "BV", "Name": "Bouvet Island"},{"Code": "BR", "Name": "Brazil"},{"Code": "IO", "Name": "British Indian Ocean Territory"},{"Code": "BN", "Name": "Brunei Darussalam"},{"Code": "BG", "Name": "Bulgaria"},{"Code": "BF", "Name": "Burkina Faso"},{"Code": "BI", "Name": "Burundi"},{"Code": "KH", "Name": "Cambodia"},{"Code": "CM", "Name": "Cameroon"},{"Code": "CA", "Name": "Canada"},{"Code": "CV", "Name": "Cape Verde"},{"Code": "KY", "Name": "Cayman Islands"},{"Code": "CF", "Name": "Central African Republic"},{"Code": "TD", "Name": "Chad"},{"Code": "CL", "Name": "Chile"},{"Code": "CN", "Name": "China"},{"Code": "CX", "Name": "Christmas Island"},{"Code": "CC", "Name": "Cocos (Keeling) Islands"},{"Code": "CO", "Name": "Colombia"},{"Code": "KM", "Name": "Comoros"},{"Code": "CG", "Name": "Congo"},{"Code": "CD", "Name": "Congo, the Democratic Republic of the"},{"Code": "CK", "Name": "Cook Islands"},{"Code": "CR", "Name": "Costa Rica"},{"Code": "CI", "Name": "C\u00f4te d'Ivoire"},{"Code": "HR", "Name": "Croatia"},{"Code": "CU", "Name": "Cuba"},{"Code": "CW", "Name": "Cura\u00e7ao"},{"Code": "CY", "Name": "Cyprus"},{"Code": "CZ", "Name": "Czech Republic"},{"Code": "DK", "Name": "Denmark"},{"Code": "DJ", "Name": "Djibouti"},{"Code": "DM", "Name": "Dominica"},{"Code": "DO", "Name": "Dominican Republic"},{"Code": "EC", "Name": "Ecuador"},{"Code": "EG", "Name": "Egypt"},{"Code": "SV", "Name": "El Salvador"},{"Code": "GQ", "Name": "Equatorial Guinea"},{"Code": "ER", "Name": "Eritrea"},{"Code": "EE", "Name": "Estonia"},{"Code": "ET", "Name": "Ethiopia"},{"Code": "FK", "Name": "Falkland Islands (Malvinas)"},{"Code": "FO", "Name": "Faroe Islands"},{"Code": "FJ", "Name": "Fiji"},{"Code": "FI", "Name": "Finland"},{"Code": "FR", "Name": "France"},{"Code": "GF", "Name": "French Guiana"},{"Code": "PF", "Name": "French Polynesia"},{"Code": "TF", "Name": "French Southern Territories"},{"Code": "GA", "Name": "Gabon"},{"Code": "GM", "Name": "Gambia"},{"Code": "GE", "Name": "Georgia"},{"Code": "DE", "Name": "Germany"},{"Code": "GH", "Name": "Ghana"},{"Code": "GI", "Name": "Gibraltar"},{"Code": "GR", "Name": "Greece"},{"Code": "GL", "Name": "Greenland"},{"Code": "GD", "Name": "Grenada"},{"Code": "GP", "Name": "Guadeloupe"},{"Code": "GU", "Name": "Guam"},{"Code": "GT", "Name": "Guatemala"},{"Code": "GG", "Name": "Guernsey"},{"Code": "GN", "Name": "Guinea"},{"Code": "GW", "Name": "Guinea-Bissau"},{"Code": "GY", "Name": "Guyana"},{"Code": "HT", "Name": "Haiti"},{"Code": "HM", "Name": "Heard Island and McDonald Islands"},{"Code": "VA", "Name": "Holy See (Vatican City State)"},{"Code": "HN", "Name": "Honduras"},{"Code": "HK", "Name": "Hong Kong"},{"Code": "HU", "Name": "Hungary"},{"Code": "IS", "Name": "Iceland"},{"Code": "IN", "Name": "India"},{"Code": "ID", "Name": "Indonesia"},{"Code": "IR", "Name": "Iran, Islamic Republic of"},{"Code": "IQ", "Name": "Iraq"},{"Code": "IE", "Name": "Ireland"},{"Code": "IM", "Name": "Isle of Man"},{"Code": "IL", "Name": "Israel"},{"Code": "IT", "Name": "Italy"},{"Code": "JM", "Name": "Jamaica"},{"Code": "JP", "Name": "Japan"},{"Code": "JE", "Name": "Jersey"},{"Code": "JO", "Name": "Jordan"},{"Code": "KZ", "Name": "Kazakhstan"},{"Code": "KE", "Name": "Kenya"},{"Code": "KI", "Name": "Kiribati"},{"Code": "KP", "Name": "Korea, Democratic People's Republic of"},{"Code": "KR", "Name": "Korea, Republic of"},{"Code": "KW", "Name": "Kuwait"},{"Code": "KG", "Name": "Kyrgyzstan"},{"Code": "LA", "Name": "Lao People's Democratic Republic"},{"Code": "LV", "Name": "Latvia"},{"Code": "LB", "Name": "Lebanon"},{"Code": "LS", "Name": "Lesotho"},{"Code": "LR", "Name": "Liberia"},{"Code": "LY", "Name": "Libya"},{"Code": "LI", "Name": "Liechtenstein"},{"Code": "LT", "Name": "Lithuania"},{"Code": "LU", "Name": "Luxembourg"},{"Code": "MO", "Name": "Macao"},{"Code": "MK", "Name": "Macedonia, the Former Yugoslav Republic of"},{"Code": "MG", "Name": "Madagascar"},{"Code": "MW", "Name": "Malawi"},{"Code": "MY", "Name": "Malaysia"},{"Code": "MV", "Name": "Maldives"},{"Code": "ML", "Name": "Mali"},{"Code": "MT", "Name": "Malta"},{"Code": "MH", "Name": "Marshall Islands"},{"Code": "MQ", "Name": "Martinique"},{"Code": "MR", "Name": "Mauritania"},{"Code": "MU", "Name": "Mauritius"},{"Code": "YT", "Name": "Mayotte"},{"Code": "MX", "Name": "Mexico"},{"Code": "FM", "Name": "Micronesia, Federated States of"},{"Code": "MD", "Name": "Moldova, Republic of"},{"Code": "MC", "Name": "Monaco"},{"Code": "MN", "Name": "Mongolia"},{"Code": "ME", "Name": "Montenegro"},{"Code": "MS", "Name": "Montserrat"},{"Code": "MA", "Name": "Morocco"},{"Code": "MZ", "Name": "Mozambique"},{"Code": "MM", "Name": "Myanmar"},{"Code": "NA", "Name": "Namibia"},{"Code": "NR", "Name": "Nauru"},{"Code": "NP", "Name": "Nepal"},{"Code": "NL", "Name": "Netherlands"},{"Code": "NC", "Name": "New Caledonia"},{"Code": "NZ", "Name": "New Zealand"},{"Code": "NI", "Name": "Nicaragua"},{"Code": "NE", "Name": "Niger"},{"Code": "NG", "Name": "Nigeria"},{"Code": "NU", "Name": "Niue"},{"Code": "NF", "Name": "Norfolk Island"},{"Code": "MP", "Name": "Northern Mariana Islands"},{"Code": "NO", "Name": "Norway"},{"Code": "OM", "Name": "Oman"},{"Code": "PK", "Name": "Pakistan"},{"Code": "PW", "Name": "Palau"},{"Code": "PS", "Name": "Palestine, State of"},{"Code": "PA", "Name": "Panama"},{"Code": "PG", "Name": "Papua New Guinea"},{"Code": "PY", "Name": "Paraguay"},{"Code": "PE", "Name": "Peru"},{"Code": "PH", "Name": "Philippines"},{"Code": "PN", "Name": "Pitcairn"},{"Code": "PL", "Name": "Poland"},{"Code": "PT", "Name": "Portugal"},{"Code": "PR", "Name": "Puerto Rico"},{"Code": "QA", "Name": "Qatar"},{"Code": "RE", "Name": "R\u00e9union"},{"Code": "RO", "Name": "Romania"},{"Code": "RU", "Name": "Russian Federation"},{"Code": "RW", "Name": "Rwanda"},{"Code": "BL", "Name": "Saint Barth\u00e9lemy"},{"Code": "SH", "Name": "Saint Helena, Ascension and Tristan da Cunha"},{"Code": "KN", "Name": "Saint Kitts and Nevis"},{"Code": "LC", "Name": "Saint Lucia"},{"Code": "MF", "Name": "Saint Martin (French part)"},{"Code": "PM", "Name": "Saint Pierre and Miquelon"},{"Code": "VC", "Name": "Saint Vincent and the Grenadines"},{"Code": "WS", "Name": "Samoa"},{"Code": "SM", "Name": "San Marino"},{"Code": "ST", "Name": "Sao Tome and Principe"},{"Code": "SA", "Name": "Saudi Arabia"},{"Code": "SN", "Name": "Senegal"},{"Code": "RS", "Name": "Serbia"},{"Code": "SC", "Name": "Seychelles"},{"Code": "SL", "Name": "Sierra Leone"},{"Code": "SG", "Name": "Singapore"},{"Code": "SX", "Name": "Sint Maarten (Dutch part)"},{"Code": "SK", "Name": "Slovakia"},{"Code": "SI", "Name": "Slovenia"},{"Code": "SB", "Name": "Solomon Islands"},{"Code": "SO", "Name": "Somalia"},{"Code": "ZA", "Name": "South Africa"},{"Code": "GS", "Name": "South Georgia and the South Sandwich Islands"},{"Code": "SS", "Name": "South Sudan"},{"Code": "ES", "Name": "Spain"},{"Code": "LK", "Name": "Sri Lanka"},{"Code": "SD", "Name": "Sudan"},{"Code": "SR", "Name": "Suriname"},{"Code": "SJ", "Name": "Svalbard and Jan Mayen"},{"Code": "SZ", "Name": "Swaziland"},{"Code": "SE", "Name": "Sweden"},{"Code": "CH", "Name": "Switzerland"},{"Code": "SY", "Name": "Syrian Arab Republic"},{"Code": "TW", "Name": "Taiwan, Province of China"},{"Code": "TJ", "Name": "Tajikistan"},{"Code": "TZ", "Name": "Tanzania, United Republic of"},{"Code": "TH", "Name": "Thailand"},{"Code": "TL", "Name": "Timor-Leste"},{"Code": "TG", "Name": "Togo"},{"Code": "TK", "Name": "Tokelau"},{"Code": "TO", "Name": "Tonga"},{"Code": "TT", "Name": "Trinidad and Tobago"},{"Code": "TN", "Name": "Tunisia"},{"Code": "TR", "Name": "Turkey"},{"Code": "TM", "Name": "Turkmenistan"},{"Code": "TC", "Name": "Turks and Caicos Islands"},{"Code": "TV", "Name": "Tuvalu"},{"Code": "UG", "Name": "Uganda"},{"Code": "UA", "Name": "Ukraine"},{"Code": "AE", "Name": "United Arab Emirates"},{"Code": "GB", "Name": "United Kingdom"},{"Code": "US", "Name": "United States"},{"Code": "UM", "Name": "United States Minor Outlying Islands"},{"Code": "UY", "Name": "Uruguay"},{"Code": "UZ", "Name": "Uzbekistan"},{"Code": "VU", "Name": "Vanuatu"},{"Code": "VE", "Name": "Venezuela, Bolivarian Republic of"},{"Code": "VN", "Name": "Viet Nam"},{"Code": "VG", "Name": "Virgin Islands, British"},{"Code": "VI", "Name": "Virgin Islands, U.S."},{"Code": "WF", "Name": "Wallis and Futuna"},{"Code": "EH", "Name": "Western Sahara"},{"Code": "YE", "Name": "Yemen"},{"Code": "ZM", "Name": "Zambia"},{"Code": "ZW", "Name": "Zimbabwe"}]

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

    try:
        db.travellers.update_one({'name': traveller}, {'$set': datatoupdate})
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

    print('Journey summary: {}'.format(datatoupdate))
    return {'status': 'success', 'message': datatoupdate}

#print(summarize_journey('Teddy'))