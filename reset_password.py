# -*- coding: utf-8 -*-

'''
    Reset password for TRAVELLER to NEW_PASSWORD
'''

from pymongo import MongoClient
from passlib.hash import sha256_crypt

TRAVELLER = 'Teddy'
NEW_PASSWORD = 1111

try:
    # Prepare DB
    client = MongoClient()
    db = client.TeddyGo
    collection_travellers = db.travellers

    # Update password
    collection_travellers.update_one({'name': TRAVELLER}, {'$set': {'secret_code': sha256_crypt.encrypt(str(NEW_PASSWORD))}})
    print('\nPassword for {} was reset to {}'.format(TRAVELLER, NEW_PASSWORD))
except Exception as e:
    print('\nFailed to reset {}\'s password. Exception: {}'.format(TRAVELLER, e))

