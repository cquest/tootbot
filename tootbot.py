import os.path
import sys
import re
import sqlite3
from datetime import datetime, timedelta
import json
import subprocess

import feedparser
from mastodon import Mastodon
import requests

if len(sys.argv) < 4:
    print("Usage: python3 tootbot.py twitter_account mastodon_login mastodon_passwd mastodon_instance [max_days [footer_tags [delay]]]")  # noqa
    sys.exit(1)

# sqlite db to store processed tweets (and corresponding toots ids)
sql = sqlite3.connect('tootbot.db')
db = sql.cursor()
db.execute('''CREATE TABLE IF NOT EXISTS tweets (tweet text, toot text,
           twitter text, mastodon text, instance text)''')

if len(sys.argv) > 4:
    instance = sys.argv[4]
else:
    instance = 'amicale.net'

if len(sys.argv) > 5:
    days = int(sys.argv[5])
else:
    days = 1

if len(sys.argv) > 6:
    tags = sys.argv[6]
else:
    tags = None

if len(sys.argv) > 7:
    delay = int(sys.argv[7])
else:
    delay = 0


source = sys.argv[1]
mastodon = sys.argv[2]
passwd = sys.argv[3]

# Create application if it does not exist
if not os.path.isfile(instance+'.secret'):
    if Mastodon.create_app(
        'tootbot',
        api_base_url='https://'+instance,
        to_file=instance+'.secret'
    ):
        print('tootbot app created on instance '+instance)
    else:
        print('failed to create app on instance '+instance)
        sys.exit(1)

try:
    mastodon_api = Mastodon(
        client_id=instance+'.secret',
        api_base_url='https://'+instance
    )
    mastodon_api.log_in(
        username=mastodon,
        password=passwd,
        scopes=['read', 'write'],
        to_file=mastodon+".secret"
    )
except:
    print("ERROR: First Login Failed!")
    sys.exit(1)


if source[:4] == 'http':
    d = feedparser.parse(source)
    twitter = None
    for t in reversed(d.entries):
        # check if this tweet has been processed
        if id in t:
            id = t.id
        else:
            id = t.title
        db.execute('SELECT * FROM tweets WHERE tweet = ? AND twitter = ?  and mastodon = ? and instance = ?', (id, source, mastodon, instance))  # noqa
        last = db.fetchone()
        dt = t.published_parsed
        age = datetime.now()-datetime(dt.tm_year, dt.tm_mon, dt.tm_mday,
                                    dt.tm_hour, dt.tm_min, dt.tm_sec)
        # process only unprocessed tweets less than 1 day old, after delay
        if last is None and age < timedelta(days=days) and age > timedelta(days=delay):
            c = t.title
            if twitter and t.author.lower() != ('(@%s)' % twitter).lower():
                c = ("RT https://twitter.com/%s\n" % t.author[2:-1]) + c
            toot_media = []
            # get the pictures...
            if 'summary' in t:
                for p in re.finditer(r"https://pbs.twimg.com/[^ \xa0\"]*", t.summary):
                    media = requests.get(p.group(0))
                    media_posted = mastodon_api.media_post(
                        media.content, mime_type=media.headers.get('content-type'))
                    toot_media.append(media_posted['id'])

            if 'links' in t:
                for l in t.links:
                    if l.type in ('image/jpg', 'image/png'):
                        media = requests.get(l.url)
                        media_posted = mastodon_api.media_post(
                            media.content, mime_type=media.headers.get('content-type'))
                        toot_media.append(media_posted['id'])

            # replace short links by original URL
            m = re.search(r"http[^ \xa0]*", c)
            if m is not None:
                l = m.group(0)
                r = requests.get(l, allow_redirects=False)
                if r.status_code in {301, 302}:
                    c = c.replace(l, r.headers.get('Location'))

            # remove ellipsis
            c = c.replace('\xa0…', ' ')

            if 'authors' in t:
                c = c + '\nSource: ' + t.authors[0].name
            c = c + '\n\n' + t.link

            if tags:
                c = c + '\n' + tags

            if toot_media is not None:
                toot = mastodon_api.status_post(c,
                                                in_reply_to_id=None,
                                                media_ids=toot_media,
                                                sensitive=False,
                                                visibility='public',
                                                spoiler_text=None)
                if "id" in toot:
                    db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )",
                            (id, toot["id"], source, mastodon, instance))
                    sql.commit()

else:
    d = feedparser.parse('http://twitrss.me/twitter_user_to_rss/?user='+source)
    twitter = source

for t in reversed(d.entries):
    # check if this tweet has been processed
    if id in t:
        id = t.id
    else:
        id = t.title
    db.execute('SELECT * FROM tweets WHERE tweet = ? AND twitter = ?  and mastodon = ? and instance = ?', (id, source, mastodon, instance))  # noqa
    last = db.fetchone()
    dt = t.published_parsed
    age = datetime.now()-datetime(dt.tm_year, dt.tm_mon, dt.tm_mday,
                                  dt.tm_hour, dt.tm_min, dt.tm_sec)
    # process only unprocessed tweets less than 1 day old, after delay
    if last is None and age < timedelta(days=days) and age > timedelta(days=delay):
        if mastodon_api is None:
            # Create application if it does not exist
            if not os.path.isfile(instance+'.secret'):
                if Mastodon.create_app(
                    'tootbot',
                    api_base_url='https://'+instance,
                    to_file=instance+'.secret'
                ):
                    print('tootbot app created on instance '+instance)
                else:
                    print('failed to create app on instance '+instance)
                    sys.exit(1)

            try:
                mastodon_api = Mastodon(
                  client_id=instance+'.secret',
                  api_base_url='https://'+instance
                )
                mastodon_api.log_in(
                    username=mastodon,
                    password=passwd,
                    scopes=['read', 'write'],
                    to_file=mastodon+".secret"
                )
            except:
                print("ERROR: First Login Failed!")
                sys.exit(1)

        c = t.title
        if twitter and t.author.lower() != ('(@%s)' % twitter).lower():
            c = ("RT https://twitter.com/%s\n" % t.author[2:-1]) + c
        toot_media = []
        # get the pictures...
        if 'summary' in t:
            for p in re.finditer(r"https://pbs.twimg.com/[^ \xa0\"]*", t.summary):
                media = requests.get(p.group(0))
                media_posted = mastodon_api.media_post(media.content, mime_type=media.headers.get('content-type'))
                toot_media.append(media_posted['id'])

        if 'links' in t:
            for l in t.links:
                if l.type in ('image/jpg', 'image/png'):
                    media = requests.get(l.url)
                    media_posted = mastodon_api.media_post(
                        media.content, mime_type=media.headers.get('content-type'))
                    toot_media.append(media_posted['id'])

        # replace short links by original URL
        m = re.search(r"http[^ \xa0]*", c)
        if m is not None:
            l = m.group(0)
            r = requests.get(l, allow_redirects=False)
            if r.status_code in {301, 302}:
                c = c.replace(l, r.headers.get('Location'))

        # remove pic.twitter.com links
        m = re.search(r"pic.twitter.com[^ \xa0]*", c)
        if m is not None:
            l = m.group(0)
            c = c.replace(l, ' ')

        # remove ellipsis
        c = c.replace('\xa0…', ' ')

        if twitter is None:
            if 'authors' in t:
                c = c + '\nSource: '+ t.authors[0].name
            c = c + '\n\n' + t.link

        if tags:
            c = c + '\n' + tags
        
        if toot_media is not None:
            toot = mastodon_api.status_post(c,
                                            in_reply_to_id=None,
                                            media_ids=toot_media,
                                            sensitive=False,
                                            visibility='public',
                                            spoiler_text=None)
            if "id" in toot:
                db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )",
                           (id, toot["id"], source, mastodon, instance))
                sql.commit()
