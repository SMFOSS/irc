import socket
import re


class IRCConnection(object):
    _sock = None
    _callbacks = {
        'PRIVMSG': [],
        'CHANMSG': [],
    }
    
    chanmsg_re = re.compile(':(?P<nick>.*?)!~\S+\s+?PRIVMSG #(?P<channel>[-\w]+)\s+:(?P<message>[^\n\r]+)')
    privmsg_re = re.compile(':(?P<nick>.*?)!~\S+\s+?PRIVMSG\s+[^:]+:(?P<message>[^\n\r]+)')
    
    def __init__(self, host, port, nick):
        self.host = host
        self.port = port
        self.nick = nick
    
    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))

    def disconnect(self):
        self.send('QUIT')
        self._sock.close()
    
    def send(self, data):
        self._sock.send('%s\r\n' % data)
    
    def authenticate(self):
        self.send('NICK %s' % self.nick)
        self.send('USER %s %s bla :%s' % (self.nick, self.host, self.nick))
    
    def join(self, channel):
        channel = channel.lstrip('#')
        self.send('JOIN #%s' % channel)
    
    def part(self, channel):
        channel = channel.lstrip('#')
        self.send('PART #%s' % channel)
    
    def register_callback(self, event, func):
        self._callbacks[event].append(func)
    
    def unregister_callback(self, event, func):
        self._callbacks[event].remove(func)
    
    def load_dispatcher(self, dispatcher_class):
        instance = dispatcher_class(self)
        
        self.register_callback('CHANMSG', instance.on_channel_message)
        self.register_callback('PRIVMSG', instance.on_private_message) 
    
    def enter_event_loop(self):
        while True:
            read_buffer = self._sock.recv(1024) # read 1K of data
            
            for line in read_buffer.splitlines():
                line = line.rstrip()
                if line.startswith('PING'):
                    self.send('PONG %s' % line.split()[1])
                else:
                    chan_match = self.chanmsg_re.match(line)
                    if chan_match:
                        for event in self._callbacks['CHANMSG']:
                            event(**chan_match.groupdict())
                    
                    priv_match = self.privmsg_re.match(line)
                    if priv_match:
                        for event in self._callbacks['PRIVMSG']:
                            event(**priv_match.groupdict())


class Dispatcher(object):
    def __init__(self, irc_connection):
        self.irc = irc_connection
    
    def get_patterns(self):
        """
        A tuple of regex -> callback where the argument signature of callback:
        
        def some_callback(sender, message, channel, is_ping):
            do some shit
        """
        raise NotImplementedError
    
    def on_channel_message(self, nick, channel, message):
        is_ping = False
        if message.startswith(self.irc.nick):
            message = re.sub('%s[^\s]*?\s' % self.irc.nick, '', message)
            is_ping = True
        for (pattern, callback) in self.get_patterns():
            if re.match(pattern, message):
                callback(nick, message, channel, is_ping)
    
    def on_private_message(self, nick, message):
        self.on_channel_message(nick, None, message)
    
    def send(self, message, channel=None, nick=None):
        if channel:
            self.irc.send('PRIVMSG #%s :%s' % (channel.lstrip('#'), message))
        elif nick:
            self.irc.send('PRIVMSG %s :%s' % (nick, message))


class IRCBot(object):
    def __init__(self, host, port, nick, channels, dispatchers):
        self.conn = IRCConnection(host, port, nick)
        self.conn.connect()
        self.conn.authenticate()
        
        for channel in channels:
            self.conn.join(channel)
        
        for dispatcher in dispatchers:
            self.conn.load_dispatcher(dispatcher)
    
    def run_forever(self):
        try:
            self.conn.enter_event_loop()
        except KeyboardInterrupt:
            self.conn.disconnect()