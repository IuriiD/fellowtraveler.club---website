from flask import Flask, request, jsonify, render_template, session
import sys
import json
#from flask_jsglue import JSGlue

app = Flask(__name__)
#jsglue = JSGlue(app)

@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('autocomplete.html')

@app.route("/get_lat_lng", methods=["GET", "POST"])
def get_lat_lng():
    print('Flask!')
    if request.method == "POST":
        print('It\'s POST!')
        latitude = request.json.get('lat')
        longitude = request.json.get('lng')
        address = request.json.get('addr')
        print('{}, {}, {}'.format(latitude, longitude, address))
    return 'Post triggered'

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')