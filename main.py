import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse

lookupUrl = "https://places.nbnco.net.au/places/v1/autocomplete?query="
detailUrl = "https://places.nbnco.net.au/places/v2/details/"

addresses = [
    'Adress here',
    'Adress here'
]

def get_data(address):
    locID = None
    try:
        r = requests.get(lookupUrl + urllib.parse.quote(address), stream=True, headers={"referer":"https://www.nbnco.com.au/"})
        locID = r.json()["suggestions"][0]["id"]
    except requests.exceptions.RequestException as e:
       return e
    try:
        r = requests.get(detailUrl + locID, stream=True, headers={"referer":"https://www.nbnco.com.au/"})
        status = r.json()
    except requests.exceptions.RequestException as e:
       return e

    return status
 
def runner():
    threads= []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for address in addresses:
            threads.append(executor.submit(get_data, address))
            
        for task in as_completed(threads):
            print(task.result()['addressDetail']['altReasonCode']) 
       
runner()

