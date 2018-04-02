import os.path
import sys
import twitter
from mastodon import Mastodon
import json
import requests
import re
import sqlite3
from datetime import datetime, date, time, timedelta

if len(sys.argv) < 4:
    print("Usage: python3 tootbot.py twitter_account mastodon_login mastodon_passwd mastodon_instance")
    sys.exit(1)

# sqlite db to store processed tweets (and corresponding toots ids)
sql = sqlite3.connect('tootbot.db')
db = sql.cursor()
db.execute('''CREATE TABLE IF NOT EXISTS tweets (tweet text, toot text, twitter text, mastodon text, instance text)''')

if len(sys.argv)>4:
    instance = sys.argv[4]
else:
    instance = 'amicale.net'

if len(sys.argv)>5:
    days = int(sys.argv[5])
else:
    days = 1

twittername = sys.argv[1]
mastodon = sys.argv[2]
passwd = sys.argv[3]

mastodon_api = None

# TO BE COMPLETED: TWITTER APP CREDENTIALS
CONSUMER_KEY = None
CONSUMER_SECRET = None
ACCESS_TOKEN = None
ACCESS_TOKEN_SECRET = None

api = twitter.Api(consumer_key = CONSUMER_KEY, consumer_secret = CONSUMER_SECRET, access_token_key = ACCESS_TOKEN, access_token_secret = ACCESS_TOKEN_SECRET, tweet_mode = 'extended')
# Fetch max. 50 statuses
feed = api.GetUserTimeline(screen_name = twittername, exclude_replies = True,
        count = 50)

for t in reversed(feed):
    # check if this tweet has been processed
    db.execute('SELECT * FROM tweets WHERE tweet = ? AND twitter = ?  and mastodon = ? and instance = ?',(t.id, twittername, mastodon, instance))
    last = db.fetchone()

    # process only unprocessed tweets less than 1 day old
    if last is None and (datetime.now()-datetime.strptime(t.created_at, "%a %b %d %H:%M:%S +0000 %Y") < timedelta(days=days)):
        if mastodon_api is None:
            # Create application if it does not exist
            if not os.path.isfile(instance+'.secret'):
                if Mastodon.create_app(
                    'tootbot',
                    api_base_url='https://'+instance,
                    to_file = instance+'.secret'
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

        #h = BeautifulSoup(t.summary_detail.value, "html.parser")
        if t.retweeted_status is not None:
            c = t.retweeted_status.full_text
            c = ("RT @%s\xa0: " % t.retweeted_status.user.screen_name) + c
        else:
            c = t.full_text
        toot_media = []
        # get the pictures...
        if t.media is not None:
            for m in t.media:
                media = requests.get(m.media_url)
                media_posted = mastodon_api.media_post(media.content, mime_type=media.headers.get('content-type'))
                toot_media.append(media_posted['id'])

        # replace t.co link by original URL
        matches = re.finditer(r"https?://[^ \n\xa0]*", c)
        length = len(c)
        for m in matches:
            l = m.group(0)
            r = requests.get(l, allow_redirects=False)
            if r.status_code in {301,302}:
                url = r.headers.get('Location')
                # Replace by original URL only if it does not result in the toot
                # exceeding 500 characters.
                new_length = length - len(l) + len(url)
                if new_length < 500:
                    c = c.replace(l,r.headers.get('Location'))
                    length = new_length

        # remove pic.twitter.com links
        m = re.search(r"pic.twitter.com[^ \xa0]*", c)
        if m != None:
            l = m.group(0)
            c = c.replace(l,' ')

        if toot_media is not None:
            toot = mastodon_api.status_post(c, in_reply_to_id=None, media_ids=toot_media, sensitive=False, visibility='public', spoiler_text=None)
            if "id" in toot:
                db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )",
                (t.id, toot["id"], twittername, mastodon, instance))
                sql.commit()
