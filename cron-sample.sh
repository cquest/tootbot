# activate virtualenv if necessary
# source /home/cquest/.virtualenvs/tootbot/bin/activate

# parameters:
# 1- twitter account to clone / or rss/atom feed URL
# 2- mastodon login
# 3- mastodon password
# 4- instance domain (https:// is automatically added)
# 5- max age (in days)
# 6- footer tags to add (optional)

python3 tootbot.py geonym_fr geonym@amicale.net **password** test.amicale.net
python3 tootbot.py cq94 cquest@amicale.net **password** test.amicale.net

python3 tootbot.py https://www.data.gouv.fr/fr/datasets/recent.atom cquest+opendata@amicale.net **password** amicale.net 2 "#dataset #opendata #datagouvfr"
