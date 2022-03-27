#!/usr/bin/env python3

import logging

from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, CallbackContext, PicklePersistence
from bs4 import BeautifulSoup
from datetime import datetime
from uuid import uuid4
from yaml import safe_load, safe_dump
import urllib, re, time, webbrowser

museums_url = "https://kpb-museum.gomus.de/api/v4/museums?locale=en&per_page=1000"
museums = {}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

def museums_touch(obj):
  tickets = f"https://kpb-museum.gomus.de/api/v4/tickets?by_bookable=true&by_free_timing=false&by_museum_ids[]={obj['id']}&by_ticket_type=time_slot&locale=en&per_page=1000&valid_at={obj['date']}"
  abort = 0
  book_date = datetime.strptime(obj['date'],'%Y-%m-%d')
  today = datetime.today()
  if book_date < today:
    return {'abort': 1, 'msg': "Book date is in the past, removing this event"}
  if (book_date - today).days > 6:
    return {'abort': 0, 'msg': ""}
  msg = []
  with urllib.request.urlopen(tickets) as tp:
    _t = safe_load(tp)
    if not len(_t['tickets']):
      return {'abort': 0, 'msg': ""}
    title = _t['tickets'][0]['title']
    quota_id = _t['tickets'][0]['quota_ids'][0]
    tickets_id = _t['tickets'][0]['id']
    capacities = f"https://kpb-museum.gomus.de/api/v4/tickets/capacities?date={obj['date']}&ticket_ids[]={tickets_id}"
    with urllib.request.urlopen(capacities) as cp:
      _c = safe_load(cp)
      slots = _c['data'][f'{quota_id}']['capacities']
      for slot in slots:
        time = datetime.strptime(slot,"%Y-%m-%dT%H:%M:%S%z")
        p_time = time.strftime("%d %b %Y, %H:%M")
        if slots[slot]:
          abort = 1
          book = f"https://shop.museumssonntag.berlin/#/tickets/time?museum_id={obj['id']}&group=timeSlot&date={obj['date']}&time={urllib.parse.quote_plus(slot)}"
          msg.append(f"<a href='{book}'>{p_time} ({slots[slot]} free)</a>")
  ret = {'abort': abort, 'msg': "\n".join(msg)}
  return ret


def start(update: Update, context: CallbackContext) -> None:
    obj = {'u': update, 'c': context}
    if len(context.job_queue.jobs())>0:
      update.message.reply_text(f'Process is started already')
      return
    if len(context.user_data)>0:
      update.message.reply_text(f'Start watching')
      context.job_queue.run_repeating(runner, 60, first=1, context=obj)
    else:
      update.message.reply_text(f'Nothing to do')

def runner(context: CallbackContext) -> None:
    u = context.job.context['u']
    c = context.job.context['c']
    to_remove=[]
    for key in c.user_data:
      book = museums_touch(c.user_data.get(key))
      if book["msg"]:
        m_id = c.user_data.get(key)['id']
        u.message.reply_text(f'<b>{museums[m_id]["title"]}</b>\n{book["msg"]}', disable_web_page_preview=True, parse_mode='HTML')
      if book["abort"] == 1:
        to_remove.append(key)
    for key in to_remove:
      del c.user_data[key]
    if (len(c.user_data) == 0):
      u.message.reply_text(f'No more URLs left, stopping. Add more URLs and /start again.')
      context.job.schedule_removal()


def watch_command(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    key = str(uuid4())
    value = update.message.text.split(' ')
    u = update.message.from_user
    if len(value) == 3:
      obj = {'id':value[1], 'date':value[2]}
      if obj in context.user_data.values():
        update.message.reply_text('Already in the list')
      else:
        context.user_data[key] = obj
        update.message.reply_text(f'Watching at <b>{museums[value[1]]["title"]}</b>, {value[2]} don\'t forget to /start', parse_mode='HTML')
        logging.info(f'{u["id"]} ({u["username"]}): {value[1]} {value[2]}')
    else:
      update.message.reply_text('Usage: /watch <museum id> <YYYY-MM-DD>')


def list_urls(update: Update, context: CallbackContext) -> None:
    if len(context.user_data)>0:
      update.message.reply_text(f'Watching at:')
    else:
      update.message.reply_text(f'List is empty')
    for key in context.user_data:
      data = context.user_data.get(key)
      update.message.reply_text(f'{data["id"]}: <b>{museums[data["id"]]["title"]}</b>, {data["date"]}',parse_mode='HTML')

def clear_urls(update: Update, context: CallbackContext) -> None:
    js = context.job_queue.jobs()
    if len(js)>0:
      update.message.reply_text(f'Stopping {len(js)} threads')
      for j in js:
        j.schedule_removal()
    update.message.reply_text(f'Clearing museums')
    context.user_data.clear()

def museums_update():
    global museums
    logging.info(f'Updating museums list')
    with urllib.request.urlopen(museums_url) as mp:
      _m = safe_load(mp)
      museums = {f"{m['id']}":m for m in _m['museums']}

def museums_list(update: Update, context: CallbackContext) -> None:
    museums_update()
    cmd = update.message.text.split(' ')
    if len(cmd)>1:
      filter = cmd[1]
      update.message.reply_text(f'Filter by "{filter}"')
    else:
      filter = ''
    list = []
    for k in museums:
      if re.match(rf'.*{filter}.*',museums[k]['title'],flags=re.IGNORECASE):
        list = list + [f"{museums[k]['title']}: /info {k}"]
    update.message.reply_text("\n".join(list))

def museum_info(update: Update, context: CallbackContext) -> None:
    cmd = update.message.text.split(' ')
    if len(cmd)>1:
      m_id = cmd[1]
      update.message.reply_text(f"ID: {m_id}\n<b>{museums[m_id]['title']}</b>\n<a href='{museums[m_id]['picture']['preview']}'>&#8205;</a>",parse_mode='HTML',disable_web_page_preview=False)
    else:
      update.message.reply_text("Usage: /info <id>")

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f'Usage:\n/help for this help\n/start to start watching\n/watch to add museum and date\n/list to list your watches\n/clear to clear the list\n/museums [search] to see all museums\n/info <id> to see museum info')

def main() -> None:
    tf = open('.token','r')
    t = tf.read()
    tf.close()
    p = PicklePersistence(filename='.museumsonntag_bot.data')
    updater = Updater(t, persistence=p)
    museums_update()
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("watch", watch_command))
    dispatcher.add_handler(CommandHandler("list", list_urls))
    dispatcher.add_handler(CommandHandler("clear", clear_urls))
    dispatcher.add_handler(CommandHandler("museums", museums_list))
    dispatcher.add_handler(CommandHandler("info", museum_info))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()