# parse a NBN web page to get a list of all suburb upgrade dates
import json
import re
import requests

from bs4 import BeautifulSoup

URL = 'https://www.nbnco.com.au/residential/upgrades/more-fibre'
content = requests.get(URL).content

results = {}

soup = BeautifulSoup(content, "html.parser")
for state_element in soup.find(id="accordion-c467de9e93").find_all("div", class_="cmp-accordion__item"):
    state = state_element.find("span", class_="cmp-accordion__title").text
    results[state] = {}
    for p in state_element.find("div", class_="cmp-text").find_all("p"):
        for suburb, date in re.findall(r"^(.*) - from (\w+ \d{4})", p.text, flags=re.MULTILINE):
            results[state][suburb] = date
    print(state, len(results[state]), results[state])

with open("results/suburb-dates.json", "w") as outfile:
    json.dump(results, outfile, indent=4)
