import os.path
import sys
import re
import html
import time
import shutil

import sqlite3
from datetime import datetime, timedelta
import json
import subprocess

import feedparser
from mastodon import Mastodon
import requests

def log(msg):
     if False:
        print('\033[96m'+msg+'\033[0m', file=sys.stderr) # cyan in console

def unredir(redir):
    # deshorten links and redirections
    r = requests.get(redir, allow_redirects=False)
    redir_count = 0
    while r.status_code in {301, 302}:
        redir_count = redir_count + 1
        if redir_count > 10:
            break
        location = r.headers.get('Location')
        if 'go.france24.com' in redir:
            # decoding hack in case "location" header is UTF-8 encoded (should not !)
            location = location.encode("latin1").decode("utf-8")
        if 'http' not in location:
            redir = re.sub(r'(https?://[^/]*).*$', r'\1', redir) + location
        else:
            redir = location
        if '//ow.ly/' in redir or '//bit.ly/' in redir:
            redir = redir.replace('https://ow.ly/', 'http://ow.ly/') # only http
            redir = requests.get(redir, allow_redirects=False).headers.get('Location')
        try:
            r = requests.get(redir, allow_redirects=False, timeout=5)
        except:
            redir = redir.replace('https://', 'http://')  # only http ?
            r = requests.get(redir, allow_redirects=False)
    return redir


def post_video(url, maxgb=32):
    # Download, recompress if needed and post a video
    subprocess.run('rm -f out.*; yt-dlp -N 8 -o out.mp4 --recode-video mp4 --no-playlist --max-filesize 100M %s' %
                (url,), shell=True, capture_output=False)
    if os.path.getsize("out.mp4") > maxgb*1024*1024:
        print('recompress/resize video')
        subprocess.run('ffmpeg -i out.mp4 -filter:v scale=1280:-1 -c:v libx265 -c:a copy resized.mp4  && mv resized.mp4 out.mp4', shell=True, capture_output=False)
    if os.path.getsize("out.mp4") > maxgb*1024*1024:
        print('recompress/resize video')
        subprocess.run('ffmpeg -i out.mp4 -filter:v scale=640:-1 -c:v libx265 -c:a copy resized.mp4  && mv resized.mp4 out.mp4', shell=True, capture_output=False)
    if os.path.getsize("out.mp4") > maxgb*1024*1024:
        print('recompress/resize video')
        subprocess.run('ffmpeg -i out.mp4 -filter:v scale=480:-1 -c:v libx265 -b:a 96k resized.mp4  && mv resized.mp4 out.mp4', shell=True, capture_output=False)
    with open("out.mp4", "rb") as file:
        video_data = file.read()
    media_posted = mastodon_api.media_post(video_data, mime_type='video/mp4')
    time.sleep(5)
    return media_posted


if len(sys.argv) < 4:
    print("Usage: python3 tootbot.py twitter_account mastodon_login mastodon_passwd mastodon_instance [max_days [footer_tags [delay]]]")  # noqa
    sys.exit(1)

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

if len(sys.argv) > 8:
    lang = sys.argv[8]
else:
    lang = 'fr'

source = sys.argv[1]
mastodon = sys.argv[2]
passwd = sys.argv[3]

if 'http' not in source:
    # switch to local account directory
    try:
        os.mkdir(source)
    except:
        pass
    os.chdir(source)

    # copy (old) global sqlite database to local account directory
    if not os.path.exists('tootbot.db'):
        shutil.copy('../tootbot.db', 'tootbot.db')

sql = sqlite3.connect('tootbot.db')
db = sql.cursor()
db.execute('''CREATE TABLE IF NOT EXISTS tweets (tweet text, toot text,
           twitter text, mastodon text, instance text)''')

# Create application if it does not exist
if not os.path.isfile(instance+'.secret'):
    if Mastodon.create_app(
        'tootbot',
        api_base_url='https://'+instance,
        to_file=instance+'.secret'
    ):
        log('tootbot app created on instance '+instance)
    else:
        log('failed to create app on instance '+instance)
        sys.exit(1)

global mastodon_api
try:
    mastodon_api = Mastodon(access_token=mastodon+".secret")
    log('logged')
except:
    try:
        mastodon_api = Mastodon(
            client_id=instance+'.secret',
            api_base_url='https://'+instance
        )
        log('login')
        mastodon_api.log_in(
            username=mastodon,
            password=passwd,
            scopes=['read', 'write'],
            to_file=mastodon+".secret"
        )
    except:
        log("ERROR: First Login Failed!")
        sys.exit(1)


print(source)
print("---------------------------")

if source[:4] == 'http':
    d = feedparser.parse(source)
    twitter = None
    print(len(d.entries))
    for t in reversed(d.entries):
        # check if this tweet has been processed
        if 'id' in t:
            id = t.id
        else:
            id = t.title

        db.execute('SELECT * FROM tweets WHERE (tweet = ? or tweet = ?) AND twitter = ?  and mastodon = ? and instance = ?',   # noqa
            (id, t.link, source, mastodon, instance))
        last = db.fetchone()
        dt = t.published_parsed
        age = datetime.now()-datetime(dt.tm_year, dt.tm_mon, dt.tm_mday,
                                    dt.tm_hour, dt.tm_min, dt.tm_sec)
        # process only unprocessed tweets less than 1 day old, after delay
        if last is None and age < timedelta(days=days) and age > timedelta(days=delay):
            try:
                alt = t.summary_detail.value
            except:
                alt = None
                pass

            if 'title' in t:
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
                for p in re.finditer(r"https://imgs.xkcd.com/[^ \"]*", t.summary):
                    print(p.group(0))
                    media = requests.get(p.group(0))
                    media_posted = mastodon_api.media_post(
                        media.content, mime_type=media.headers.get('content-type'))
                    toot_media.append(media_posted['id'])

                for p in re.finditer(r"https://i.redd.it/[a-zA-Z0-9]*.(gif/jpg/mp4/png|webp)", t.summary):
                    mediaUrl = p.group(0)
                    try:
                        media = requests.get(mediaUrl)
                        media_posted = mastodon_api.media_post(
                            media.content, mime_type=media.headers.get('content-type'))
                        toot_media.append(media_posted['id'])
                    except:
                        print('Could not upload media to Mastodon! ' + mediaUrl)

            if 'links' in t:
                for l in t.links:
                    if l.type in ('image/gif', 'image/jpg', 'image/png', 'image/webp'):
                        media = requests.get(l.url, headers = {'User-agent': 'Mozilla/5.0'})
                        if media.status_code == 200:
                            media_posted = mastodon_api.media_post(
                                media.content, mime_type=media.headers.get('content-type'))
                            toot_media.append(media_posted['id'])

            # replace short links by original URL
            m = re.search(r"http[^ \xa0]*", c)
            if m is not None:
                l = m.group(0)
                try:
                    redir = unredir(l)
                    c = c.replace(l, redir)
                except:
                    print('Cannot resolve link redirect: ' + l)

            # remove ellipsis
            c = c.replace('\xa0…', ' ')

            if 'authors' in t:
                c = c + '\nSource: ' + t.authors[0].name
            c = c + '\n\n' + t.link

            # replace links to reddit by libreddit ones
            c = c.replace('old.reddit.com', 'libreddit.net')
            c = c.replace('reddit.com', 'libreddit.net')

            if tags:
                c = c + '\n' + tags

            if toot_media is not None:
                toot = mastodon_api.status_post(c,
                                                in_reply_to_id=None,
                                                media_ids=toot_media,
                                                sensitive=False,
                                                visibility='unlisted',
                                                spoiler_text=None, language=lang)
                if "id" in toot:
                    db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )",
                            (t.link, toot["id"], source, mastodon, instance))
                    sql.commit()

print("---------------------------")
print()
