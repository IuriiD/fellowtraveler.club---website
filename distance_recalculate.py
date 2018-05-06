# -*- coding: utf-8 -*-

from pymongo import MongoClient
import requests
from keys import GOOGLE_MAPS_API_KEY

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