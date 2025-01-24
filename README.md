# TootBot

A small python 3.x script to replicate RSS and posts on bluesky to a mastodon account.

The script only need mastodon login/pass to post toots.

It gets the BS posts thru their public API.
- externally hosted pictures or videos are retrieved with **yt-dlp** and uploaded to mastodon

It can also toot RSS/atom feeds (see cron-example.sh).

A sqlite database is used to keep track of tweets than have been tooted.

Threads are maintained as far as possible, but replies and reposts and not replicated.

The script is simply called by a cron job and can run on any server (does not have to be on the mastodon instance server).

## Setup

```shell
# clone this repo
git clone https://github.com/cquest/tootbot.git
cd tootbot

# install required python modules
pip3 install -r requirements.txt

# install additional required software
sudo apt install jq ffmpeg
```

## Useage

`python3 tootbot.py <twitter_pseudo> <mastodon_account> <mastodon_password> <mastodon_domain> [max_items [tags_to_add]]`

Example:

`python3 tootbot.py geonym_fr geonym@mastodon.mydomain.org **password** mastodon.mydomain.org`

It's up to you to add this in your crontab :)

With a plain RSS/atom feed:

`python3 tootbot.py https://www.data.gouv.fr/fr/datasets/recent.atom cquest+opendata@amicale.net **password** amicale.net 2 "#dataset #opendata #datagouvfr"`
