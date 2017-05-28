# activate virtualenv if necessary
# source /home/cquest/.virtualenvs/tootbot/bin/activate

# parameters:
# 1- twitter account to clone
# 2- mastodon login
# 3- mastodon password
# 4- instance domain (https:// is automatically added)

python tootbot.py geonym_fr geonym@amicale.net **password** test.amicale.net
python tootbot.py cq94 cquest@amicale.net **password** test.amicale.net
