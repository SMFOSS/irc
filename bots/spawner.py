import gevent
from gevent.monkey import patch_socket; patch_socket()
from gevent import spawn
from irc import Dispatcher, IRCBot


host = 'irc.freenode.net'
port = 6667
nick = 'spawnbot'
rooms = ['#lawrence-botwars']

MAX_BOTS = 11
BOTS = []


class SpawningDispatcher(Dispatcher):

    def spawn(self, sender, message, channel, is_ping, reply):
        if not is_ping or not channel:
            return
        try:
            n = int(message.split()[-1])
        except ValueError:
            return "%s doesn't look like a number" % message.split()[-1]

        if n < 0:
            reply('removing %s bots' % n)
            for x in range(abs(n)):
                if len(BOTS) == 1:
                    continue
                b = BOTS.pop()
                b.conn.disconnect()
                del(b)
            return

        if len(BOTS) + n > MAX_BOTS:
            return 'sorry, would exceed maximum of %s bots' % MAX_BOTS

        reply('spawning %s bots' % n)
        for x in range(n):
            if len(BOTS) >= MAX_BOTS:
                return 'reached max'
            add_bot('%s%s' % (nick, len(BOTS)))

    def sleep(self, sender, message, channel, is_ping, reply):
        if not channel:
            return
        n = float(message.split()[-1])
        gevent.sleep(n)
        return 'slept %ss' % n

    def get_patterns(self):
        return (
            ('^spawn', self.spawn),
            ('^sleep', self.sleep),
        )


# start telnet backdoor on port 2000
from gevent.backdoor import BackdoorServer
server = BackdoorServer(('127.0.0.1', 2000), locals=locals())
server.start()

def add_bot(nick):
    bot = IRCBot(host, port, nick, rooms, [SpawningDispatcher])
    BOTS.append(bot)
    g = spawn(bot.run_forever)
    return bot, g

master, g = add_bot(nick)

g.join() # run until the master bot exits
