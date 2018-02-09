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
