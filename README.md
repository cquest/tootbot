# TootBot

A small python 3.x script to replicate tweets on a mastodon account.

The script only need mastodon login/pass to post toots.

It gets the tweets from RSS available at http://twitrss.me, then does some cleanup on the content:
- twitter tracking links (t.co) are dereferenced
- twitter hosted pictures are retrieved and uploaded to mastodon

It can also toot RSS/atom feeds (see cron-example.sh).

A sqlite database is used to keep track of tweets than have been tooted.


This script is in use for a few accounts:
- cq94 -> https://amicale.net/@cquest (original author mastodon account)
- osm_fr -> https://fr.osm.social/@osm_fr
- sotmfr -> https://fr.osm.social/@sotmfr
- macbidouille -> <https://amicale.net/@macbidouille
- nextinpact -> <https://amicale.net/@nextinpact
- opendata -> https://amicale.net/@opendata

The script is simply called by a cron job and can run on any server (does not have to be on the mastodon instance server).

## Setup

```
# clone this repo
git clone https://github.com/cquest/tootbot.git
cd tootbot

# install required python modules
pip3 install -r requirements.txt
```

## Useage

`python3 tootbot.py <twitter_pseudo> <mastodon_account> <mastodon_password> <mastodon_domain> [max_items [tags_to_add]]`

Example:

`python3 tootbot.py geonym_fr geonym@mastodon.mydomain.org **password** mastodon.mydomain.org`

It's up to you to add this in your crontab :)

With a plain RSS/atom feed:

`python3 tootbot.py https://www.data.gouv.fr/fr/datasets/recent.atom cquest+opendata@amicale.net **password** amicale.net 2 "#dataset #opendata #datagouvfr"`
