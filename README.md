# TootBot

A small python 3.x script to replicate tweets on a mastodon account.

The script only need mastodon login/pass to post toots.

It gets the tweets from RSS available at http://twitrss.me, then does some cleanup on the content:
- twitter tracking links (t.co) are dereferenced
- twitter hosted pictures are retrieved and uploaded to mastodon

A sqlite database is used to keep track of tweets than have been tooted.


This script is in use for a few accounts:
- cq94 -> https://amicale.net/@cquest
- Etalab -> https://mastodon.etalab.gouv.fr/@etalab
- datagouvfr -> https://mastodon.etalab.gouv.fr/@datagouvfr
- osm_fr -> https://fr.osm.social/@osm_fr
- sotmfr -> https://fr.osm.social/@sotmfr

The script is simply called by a cron job and can run on any server (does not have to be on the mastodon instance server).

## How to install and run (suggestion)

```bash
$ cd /tmp
$ git clone https://github.com/halcy/Mastodon.py
$ mkvirtualenv tootbot -p /usr/bin/python3
$ pip install ./Mastodon.py/
$ # cleanup
$ rm Mastodon.py
$ pip install feedparser
$ which python
/home/user/.virtualenvs/tootbot/bin/python
```
Take note of this last answer : this is the Python executable we'll use in the next command: 

Then run 
```bash
/home/user/.virtualenvs/tootbot/bin/python tootbot twitter_account mastodon_login mastodon_pass mastodon_instance
```
(then make your own script based on cron-sample.sh!)
