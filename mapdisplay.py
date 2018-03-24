from flask import Flask, render_template, request
from flask_googlemaps import GoogleMaps
from flask_googlemaps import Map
from pymongo import MongoClient
from keys import GOOGLE_MAPS_API_KEY

app = Flask(__name__)
GoogleMaps(app)

# you can set key as config
app.config['GOOGLEMAPS_KEY'] = GOOGLE_MAPS_API_KEY

@app.route("/")
def mapview():
    # Connect to DB 'TeddyGo'
    client = MongoClient()
    db = client.TeddyGo
    teddys_locations = db['Teddy'].find().sort([('_id', -1)])

    start_lat = None
    start_long = None
    mymarkers = []
    for location in teddys_locations:
        if start_lat == None:
            start_lat = location['latitude']
            start_long = location['longitude']
        author = location['author']
        comment = location['comment']
        photos = location['photos']
        infobox = ''
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

    # creating a map in the view
    teddy_locations = Map(
        identifier="teddy_locations",
        lat=start_lat,
        lng=start_long,
        zoom=8,
        language="en",
        style="height:480px;width:720px;margin:1;",
        markers=mymarkers,
        fit_markers_to_bounds = True
    )

    return render_template('example.html', teddy_locations=teddy_locations)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
