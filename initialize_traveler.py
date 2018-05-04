# -*- coding: utf-8 -*-

'''
    Initialise traveller - create a document in db TeddyGo >> travellers >> <Traveller>
'''

import os
from pymongo import MongoClient
from passlib.hash import sha256_crypt

TRAVELLER = 'Stone'
INITIAL_PASSWORD = 1111
TRAVELLERS_DIR = os.path.join('static', 'uploads', TRAVELLER, 'service')

try:
    # Prepare DB
    client = MongoClient()
    db = client.TeddyGo
    collection_travellers = db.travellers

    # Check if such traveler hasn't been initialized already
    if collection_travellers.find({'name': TRAVELLER}).count() > 0:
        print('Traveler {} already exists'.format(TRAVELLER))
    else:
        # Prepare default document
        teddy_document = {
            'name': TRAVELLER,
            'secret_code': sha256_crypt.encrypt(str(INITIAL_PASSWORD)),
            'distance_from_home': 0,
            'origin': '',
            'total_countries': 0,
            'start_date': '',
            'start_date_service': None,
            'locations_lat_long': [],
            'countries_visited': [],
            'total_locations': 0,
            'total_distance': 0
        }

        # Insert document
        traveller_doc_id = collection_travellers.insert_one(teddy_document).inserted_id
        print('\nTraveller {} successfully initiated with password {}'.format(TRAVELLER, INITIAL_PASSWORD))

        # Create directory for location photos and service images. The following images should be provided:
        # 1) <Traveler>.jpg
        # 2) biography.jpg
        # 3) how_secret_code_looks_like.jpg (may be one for all travelers)
        if not os.path.exists(TRAVELLERS_DIR):
            os.makedirs(TRAVELLERS_DIR)
            print('\nDirectory {} created for traveler\'s images\nPlease do not forget to upload "service" images <Traveler>.jpg, biography.jpg and how_secret_code_looks_like.jpg'.format(TRAVELLERS_DIR))
        else:
            print(
                '\nDirectory {} already exists. \nPlease make sure that you provided "service" images {}.jpg, biography.jpg and how_secret_code_looks_like.jpg'.format(
                    TRAVELLERS_DIR, TRAVELLER))
except Exception as e:
    print('\nFailed to initialize traveller {}. Exception: {}'.format(TRAVELLER, e))