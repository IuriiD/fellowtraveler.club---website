#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import requests
from flask import request, flash
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
    locations_history = []
    teddy_locations = Map(
        identifier="teddy_locations",
        lat=37.4419,
        lng=-122.1419,
        zoom=10,
        language="en",
        style="height:720px;width:400px;margin:1;",
        markers=[]
    )

    for location in teddys_locations:
        location_data = {
            'author': location['author'],
            'location': location['location'],
            'time': '{} {}'.format(location['_id'].generation_time.date(), location['_id'].generation_time.time()),
            'comment': location['comment'],
            'photos': location['photos']
        }
        locations_history.append(location_data)
        lat = float(location_data['location'].split(', ')[0])
        long = float(location_data['location'].split(', ')[1])
        teddy_locations['markers'].append(
            {
                'icon': 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
                'lat': lat,
                'lng': long,
                'infobox': '{} - {}'.format(location_data['author'], location_data['time'])
            }
        )

    return [locations_history, teddy_locations]