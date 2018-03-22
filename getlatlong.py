from flask import Flask, request, jsonify, render_template
import sys
from flask_jsglue import JSGlue

app = Flask(__name__)
jsglue = JSGlue(app)

@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('autocomplete.html')

@app.route("/get_lat_lng", methods=["GET", "POST"])
def get_lat_lng():
    print('Flask!')
    if request.method == "GET":
        print(request.args)
'''     print('POST!')
        data = {}
        data['lat'] = request.json['lat']
        data['lng'] = request.json['lng']
        print(str(data))
        return jsonify(data)
'''

# Run Flask server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')