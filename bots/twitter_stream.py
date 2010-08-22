import gevent
from gevent import spawn
from gevent.monkey import patch_socket; patch_socket()
from irc import Dispatcher, IRCBot
import tweetstream


host = 'irc.freenode.net'
port = 6667
nick = 'twatterbotter'
channels = ['#lawrence-botwars']

twitter_auth = ('irctwatbot', 'twizatbizot')

def require_direct_channel_ping(func):
    def f(self, sender, message, channel, is_ping, reply):
        if not is_ping or not channel:
            return
        return func(self, sender, message, channel, is_ping, reply)
    return f

def collect_tweets(tracked_terms, conn):
    stream = tweetstream.TrackStream(twitter_auth[0], twitter_auth[1], tracked_terms)
    for tweet in stream:
        message = '%s by %s' % tuple(map(clean, (tweet['text'], tweet['user']['name'])))
        for channel in channels:
            conn.send('PRIVMSG #%s :%s' % (channel.lstrip('#'), message))

def clean(s):
    return s.encode('ascii', 'xmlcharrefreplace')

class TwitterStreamingDispatcher(Dispatcher):

    def __init__(self, *args):
        super(TwitterStreamingDispatcher, self).__init__(*args)
        self._watched_terms = []
        self._tracker = None

    @require_direct_channel_ping
    def watch(self, sender, message, channel, is_ping, reply):
        term = ' '.join(message.split()[1:])
        if term not in self._watched_terms:
            self._watched_terms.append(term)
        reply('watching: %s' % self._watched_terms)
        self.update_tracker(reply)

    @require_direct_channel_ping
    def unwatch(self, sender, message, channel, is_ping, reply):
        term = ' '.join(message.split()[1:])
        while term in self._watched_terms:
            self._watched_terms.remove(term)
        reply('watching: %s' % self._watched_terms)
        self.update_tracker(reply)

    def update_tracker(self, reply):
        if self._tracker:
            reply('closing existing tracker')
            spawn(self._tracker.kill).join()
        reply('starting new tracker')
        self._tracker = spawn(collect_tweets, self._watched_terms, self.irc)

    def get_patterns(self):
        return (
            ('^watch', self.watch),
            ('^unwatch', self.unwatch),
        )

while True:
    bot = IRCBot(host, port, nick, channels, [TwitterStreamingDispatcher])
    spawn(bot.run_forever).join()
