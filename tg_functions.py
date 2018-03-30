#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import requests
from flask import request, flash, url_for
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import datetime
#import googlemaps

VALID_IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp"
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
    return any([url.endswith(e.lower()) for e in extension_list])

# Validating image mimetype
def valid_url_mimetype(url, mimetype_list=VALID_IMAGE_MIMETYPES):
    # http://stackoverflow.com/a/10543969/396300
    mimetype, encoding = mimetypes.guess_type(url)
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
            'alert alert-warning alert-dismissible fade show')
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
        print("location_data: {}".format(location_data))
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
    print("Locations N: {}".format(len(allhistory)))
    print("Last location shown #: {}".format(last_location))

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
            print("imageUrl: {}".format(imageUrl))
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