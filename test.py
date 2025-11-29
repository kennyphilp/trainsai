import requests
import json

url = "https://huxley.apphb.com/all/gtw/from/vic/1?accessToken==509d80dc-436d-43f7-bfa6-21786675d997"

response = requests.get(url)

if response.status_code == 200:
    resp = response.json()
    if resp.get("trainServices") and len(resp["trainServices"]) > 0:
        message = f"The next train to arrive at {resp['locationName']} from {resp['filterLocationName']} will get in at {resp['trainServices'][0]['sta']}"
        print(message)
    else:
        message = f"Sorry, no trains from {resp['filterLocationName']} arriving soon"
        print(message)