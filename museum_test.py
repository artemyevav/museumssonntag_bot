#!/usr/bin/env python3

from bs4 import BeautifulSoup
import urllib, re, time, webbrowser
from datetime import datetime
from yaml import safe_load, safe_dump

museum = 71
date = '2022-03-06'
tickets = f"https://kpb-museum.gomus.de/api/v4/tickets?by_bookable=true&by_free_timing=false&by_museum_ids[]={museum}&by_ticket_type=time_slot&locale=en&per_page=1000&valid_at={date}"
museums = "https://kpb-museum.gomus.de/api/v4/museums?locale=en&per_page=1000"

with urllib.request.urlopen(museums) as mp:
  _m = safe_load(mp)
  mus = {m['id']:m for m in _m['museums']}

with urllib.request.urlopen(tickets) as tp:
  _t = safe_load(tp)
  title = _t['tickets'][0]['title']
  quota_id = _t['tickets'][0]['quota_ids'][0]
  tickets_id = _t['tickets'][0]['id']
  capacities = f"https://kpb-museum.gomus.de/api/v4/tickets/capacities?date={date}&ticket_ids[]={tickets_id}"
#  print (mus[museum])
  with urllib.request.urlopen(capacities) as cp:
    _c = safe_load(cp)
    slots = _c['data'][f'{quota_id}']['capacities']
    for slot in slots:
      time = datetime.strptime(slot,"%Y-%m-%dT%H:%M:%S%z")
      p_time = time.strftime("%d %b %Y, %H:%M")
      if slots[slot]:
        book = f"https://shop.museumssonntag.berlin/#/tickets/time?museum_id={museum}&group=timeSlot&date={date}&time={slot}"
        print(f"{p_time} -> {slots[slot]} -> {book}")

