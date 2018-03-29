import requests, json
from keys import DIALOFLOW_CLIENT_ACCESS_TOKEN

URL = 'https://api.dialogflow.com/v1/query?v=20170712'
HEADERS = {'Authorization': 'Bearer ' + DIALOFLOW_CLIENT_ACCESS_TOKEN, 'content-type': 'application/json'}

query = 'How are you?'
sessionID = '1234567890'
lang_code = 'en'

payload = {'query': query, 'sessionId': sessionID, 'lang': lang_code}
r = requests.post(URL, data=json.dumps(payload), headers=HEADERS).json()
print(r.get('result').get('fulfillment').get('speech'))
