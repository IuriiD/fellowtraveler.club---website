from flask import Flask, render_template, request
from flask_googlemaps import GoogleMaps
from flask_googlemaps import Map
from keys import GOOGLE_MAPS_API_KEY

app = Flask(__name__)
GoogleMaps(app)

# you can set key as config
app.config['GOOGLEMAPS_KEY'] = GOOGLE_MAPS_API_KEY

@app.route("/")
def mapview():
    # creating a map in the view
    teddy_locations = Map(
        identifier="teddy_locations",
        lat=37.4419,
        lng=-122.1419,
        zoom=18,
        language="en",
        style="height:720px;width:720px;margin:1;",
        markers=[
          {
             'icon': 'http://maps.google.com/mapfiles/ms/icons/green-dot.png',
             'lat': 37.4419,
             'lng': -122.1419,
             'infobox': "<b>Hello World<img src='static/img/teddy_photo.jpg' width='40px'/>Again</b>"
          },
          {
             'icon': 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png',
             'lat': 37.4300,
             'lng': -122.1400,
             'infobox': "<b>Hello World from other place</b>"
          },
            {
                'icon': 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
                'lat': 37.4300,
                'lng': -122.1440,
                'infobox': "<b>Hello3</b>"
            }
        ]
    )

    return render_template('example.html', teddy_locations=teddy_locations)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
