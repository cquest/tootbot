#! /bin/env python3

import os.path, sys, re, time, shutil, sqlite3, json, subprocess
from datetime import datetime, timedelta

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

if 'bsky' in source:
    source = source.replace('bsky:','')
    url = 'https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=%s&filter=posts_with_replies&includePins=false' % source
    log('GET '+url)
    get_bsky = requests.get(url)
    bsky = json.loads(get_bsky.text)
    print(len(bsky['feed']))
    for t in reversed(bsky['feed']):
        if t['post']['author']['handle'] != source:
            log('repost, skipped')
            continue

        db.execute('SELECT * FROM tweets WHERE (tweet = ?) AND twitter = ?  and mastodon = ? and instance = ?',   # noqa
            (t['post']['uri'], source, mastodon, instance))
        last = db.fetchone()
        if last:
            log('already tooted : '+t['post']['uri'])
            continue

        log(json.dumps(t, indent=4))
        if 'post' in t:
            reply_masto = None
            if 'reply' in t:
                reply = t['reply']
                db.execute('SELECT toot FROM tweets WHERE (tweet = ?) AND twitter = ?  and mastodon = ? and instance = ?',   # noqa
                                (reply['parent']['uri'], source, mastodon, instance))
                last = db.fetchone()
                if last:
                    reply_masto = last[0]
                    log('reply %s -> %s' %(reply['parent']['uri'],reply_masto))
                else:
                    log('reply')
                    continue

            toot_media = []
            language = lang
            c = t['post']['record']['text']

            if 'langs' in t['post']:
                language = t['post']['lang'][0]

            if 'facets' in t['post']['record']:
                for facet in reversed(t['post']['record']['facets']):
                    if facet['features'][0]['$type'] == 'app.bsky.richtext.facet#link':
                        b = c.encode()
                        old = b[facet['index']['byteStart']:facet['index']['byteEnd']]
                        c = c.replace(old.decode(),facet['features'][0]['uri'])

            if 'embed' in t['post']['record']:
                embed = t['post']['record']['embed']
                embed_type = embed['$type']
                if embed_type == 'app.bsky.embed.external':
                    # check that the link is not already in the text
                    if embed['external']['uri'] not in c:
                        c = c + '\n\n' + embed['external']['uri']

            if 'embed' in t['post']['record']:
                embed = t['post']['embed']
                if 'app.bsky.embed.images' in embed['$type']:
                    for img in embed['images']:
                        print(img['fullsize'])
                        media = requests.get(img['fullsize'], headers = {'User-agent': 'Mozilla/5.0'})
                        if media.status_code == 200:
                            media_posted = mastodon_api.media_post(
                                media.content, mime_type=media.headers.get('content-type'))
                            toot_media.append(media_posted['id'])
                elif 'app.bsky.embed.video' in embed['$type']:
                    media_posted = post_video(embed['playlist'])
                    toot_media.append(media_posted['id'])
                elif 'app.bsky.embed.external' in embed['$type']:
                    if 'youtube.com' in embed['external']['uri']:
                        media_posted = post_video(embed['external']['uri'])
                        toot_media.append(media_posted['id'])
                        c = c.replace(embed['external']['uri'],'')
                elif 'app.bsky.embed.recordWithMedia' in embed['$type']:
                    log('unhandled app.bsky.embed.recordWithMedia')
                    continue
                    if 'app.bsky.embed.video' in embed['media']['$type']:
                        media_posted = post_media(embed['media']['playlist'])
                        toot_media.append(media_posted['id'])
                elif 'app.bsky.embed.record' in embed['$type']:
                    log('unhandled app.bsky.embed.record')
                    continue

            retries = 10
            toot = None
            while toot is None and retries > 0:
                try:
                    toot = mastodon_api.status_post(c,
                                        in_reply_to_id=reply_masto,
                                        media_ids=toot_media,
                                        sensitive=False,
                                        visibility='unlisted',
                                        spoiler_text=None,
                                        language=language)
                except:
                    log('delayed due to media processing')
                    time.sleep(10)
                    retries = retries - 1
                    pass

            if "id" in toot:
                db.execute("INSERT INTO tweets VALUES ( ? , ? , ? , ? , ? )",
                        (t['post']['uri'], toot["id"], source, mastodon, instance))
                sql.commit()


elif source[:4] == 'http':
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
                     
            if 'media_content' in t:
                for m in t.media_content:
                    if m['type'] in ('image/gif', 'image/jpg', 'image/jpeg', 'image/png', 'image/webp'):
                        media = requests.get(m['url'], headers = {'User-agent': 'Mozilla/5.0'})
                        if media.status_code == 200:
                            try:
                                media_posted = mastodon_api.media_post(
                                    media.content,
                                    mime_type=media.headers.get('content-type'),
                                    description=alt)
                            except:
                                # resize picture
                                height = int(m['height'])
                                width = int(m['width'])
                                height = str(int(1.0 * height / width * 1024))
                                width = '1024'
                                new_url = m['url'].replace('height='+m['height'], 'height='+height).replace('width='+m['width'], 'width='+width)
                                media = requests.get(new_url, headers = {'User-agent': 'Mozilla/5.0'})
                                if media.status_code == 200:
                                    media_posted = mastodon_api.media_post(
                                        media.content,
                                        mime_type=media.headers.get('content-type'),
                                        description=alt)
                            toot_media.append(media_posted['id'])
                            break
            elif 'links' in t:
                for l in t.links:
                    if l.type in ('image/gif', 'image/jpg', 'image/jpeg', 'image/png', 'image/webp'):
                        media = requests.get(l.url, headers = {'User-agent': 'Mozilla/5.0'})
                        if media.status_code == 200:
                            media_posted = mastodon_api.media_post(
                                media.content, mime_type=media.headers.get('content-type'))
                            toot_media.append(media_posted['id'])
                            break

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

            if ('marianne' in mastodon) and 'summary' in t:
                c = c + '\n\n' + t.summary
                if len(c)>450:
                    fin = c[450:].split(' ')
                    c = c[:450] + fin[0]
                    if len(fin)>1:
                        c = c + '…'

            if 'authors' in t:
                c = c + ('\n(%s) ' % t.authors[0].name)
                if 'ATEXO' in t.authors[0].name:
                    continue

            c = c + '\n\n' + t.link
            c = re.sub(r'(\?|&)utm.*$', r'\1utm_medium=Social&utm_source=Mastodon', c)

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
