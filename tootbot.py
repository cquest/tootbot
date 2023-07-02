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


def unredir(redir):
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


print(source)
print("---------------------------")

if source[:4] == 'http':
    d = feedparser.parse(source)
    twitter = None
    print(len(d.entries))
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
                                                visibility='public',
                                                spoiler_text=None)
                if "id" in toot:
                    db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )",
                            (id, toot["id"], source, mastodon, instance))
                    sql.commit()

else:
    # cleanup local database after migration from the global one
    db.execute("DELETE FROM tweets WHERE twitter != ?", (source,))
    sql.commit()
    db.execute("VACUUM")

    subprocess.run('rm -f tweets.*json; twint -u %s -tl --limit 10 --json -o tweets.sjson; jq -s . tweets.sjson > tweets.json' %
                   (source,), shell=True, capture_output=True)
    d = json.load(open('tweets.json','r'))
    twitter = source

    print(len(d))
    for t in reversed(d):
        c = html.unescape(t['tweet'])
        # do not toot twitter replies
        if 'reply_to' in t and len(t['reply_to'])>0:
            # print('Reply:',c)
            continue
        # do not toot twitter quoted RT
        if 'quote_url' in t and t['quote_url'] != '':
            # print('Quoted:', c)
            continue

        # check if this tweet has been processed
        # new id from status link to support threads
        id = t['link'].split('/')[-1]
        db.execute('SELECT * FROM tweets WHERE (tweet like ? or tweet = ?) AND twitter = ? and mastodon = ? and instance = ?', (id+'%', t['id'], source, mastodon, instance))  # noqa
        if db.fetchone():
            continue

        # detect threads
        in_reply_to = None
        if 'conversation_id' in t and t['conversation_id'] not in t['link']:
            db.execute('SELECT toot FROM tweets WHERE tweet like ? AND twitter = ? ORDER BY tweet DESC LIMIT 1', ('% '+t['conversation_id'], source))  # noqa
            thread = db.fetchone()
            if thread:
                in_reply_to = thread[0].split()[-1]
                print("Thread :", t['conversation_id'],
                      t['link'], thread[0], in_reply_to)


        if c[-1] == "…":
            continue

        toot_media = []
        if twitter and t['username'].lower() != twitter.lower():
            c = ("RT https://twitter.com/%s\n" % t['username']) + c
            # get the pictures...
            for p in re.finditer(r"https://pbs.twimg.com/[^ \xa0\"]*", t['tweet']):
                media = requests.get(p.group(0))
                media_posted = mastodon_api.media_post(
                    media.content, mime_type=media.headers.get('content-type'))
                toot_media.append(media_posted['id'])

        if 'photos' in t:
            for url in t['photos']:
                # print('photo', url)
                try:
                    media = requests.get(url.replace(
                            'https://pbs.twimg.com/', 'https://nitter.net/pic/orig/'))
                    # print("received nitter", media.headers.get('content-type'))
                    media_posted = mastodon_api.media_post(
                        media.content, mime_type=media.headers.get('content-type'))
                    # print("posted")
                    toot_media.append(media_posted['id'])
                except:
                    media = requests.get(url)
                    # print("received twitter", media.headers.get('content-type'))
                    media_posted = mastodon_api.media_post(
                        media.content, mime_type=media.headers.get('content-type'))
                    # print("posted")
                    toot_media.append(media_posted['id'])


        # replace short links by original URL
        links = re.findall(r"http[^ \xa0]*", c)
        for l in links:
            redir = unredir(l)
            m = re.search(r'twitter.com/.*/photo/', redir)
            if m is None:
                c = c.replace(l, redir)
            else:
                c = c.replace(l, '')

            m = re.search(r'(twitter.com/.*/video/|youtube.com)', redir)
            if m is None:
                c = c.replace(l, redir)
            else:
                video = redir
                # print('video:', video)
                video_json = subprocess.run('yt-dlp -s -j %s' %
                               (video,), shell=True, capture_output=True)
                video_info = json.loads(video_json.stdout)
                if video_info['duration'] < 600:
                    # print('lien:', l)
                    c = c.replace(l, '')
                    subprocess.run('rm -f out.*; yt-dlp -N 8 -o out.mp4 --recode-video mp4 --no-playlist --max-filesize 100M %s' %
                                (video,), shell=True, capture_output=False)
                    # print("received")
                    try:
                        file = open("out.mp4", "rb")
                        video_data = file.read()
                        file.close()
                        media_posted = mastodon_api.media_post(video_data, mime_type='video/mp4')
                        c = c.replace(video, '')
                        # print("posted")
                        toot_media.append(media_posted['id'])
                        os.remove("out.mp4")
                    except:
                        pass
                else:
                    print("video duration > 600s : ", video_info['duration'])

        # remove pic.twitter.com links
        m = re.search(r"pic.twitter.com[^ \xa0]*", c)
        if m is not None:
            l = m.group(0)
            c = c.replace(l, ' ')

        # remove ellipsis
        c = c.replace('\xa0…', ' ')

        #c = c.replace('  ', '\n').replace('. ', '.\n')

        # replace links to twitter by nitter ones
        c = c.replace('/twitter.com/', '/nitter.net/')

        # replace utm_? tracking
        c = re.sub('\?utm.*$', '?utm_medium=Social&utm_source=Mastodon', c)

        if tags:
            c = c + '\n' + tags

        try:
            if len(toot_media)>0:
                time.sleep(5)
            toot = mastodon_api.status_post(c,
                                        in_reply_to_id=in_reply_to,
                                        media_ids=toot_media,
                                        sensitive=False,
                                        visibility='unlisted',
                                        spoiler_text=None)
        except:
            print("delay")
            time.sleep(30)
            toot = mastodon_api.status_post(c,
                                            in_reply_to_id=in_reply_to,
                                            media_ids=toot_media,
                                            sensitive=False,
                                            visibility='unlisted',
                                            spoiler_text=None)
            pass

        #break
        if "id" in toot:
            db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )", (id+' '+t['conversation_id'], toot["id"], source, mastodon, instance))
            sql.commit()
            print(source, ": tweet created at",t['created_at'])

print("---------------------------")
print()
