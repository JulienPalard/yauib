#!/usr/bin/env python
import logging
from contextlib import closing
import socket
import argparse
import select
import sys
from textwrap import wrap
import os
import subprocess
from irclib import IRC
from time import sleep


class Socket(object):
    """
    Socket is a struct containing a socket and two handlers :
    on_write and on_read.

    This class is used by Network to store each sockets with its
    handlers.
    """
    __slots__ = ("socket", "on_read", "on_write", "sockets")

    def __init__(self, sock, on_read=None, on_write=None):
        self.socket = sock
        if on_read:
            self.on_read = on_read
        if on_write:
            self.on_write = on_write


class Network(object):
    """
    The Network class provides an easy way to listen on a TCP port.
    It internally use select to block waiting for data, and permits
    you to manually add and remove sockets to be monitored.

    Basic usage is :
    net = Network()
    net.listen('127.0.0.1', 4242, sys.stdout.write)
    net.run_forever()

    public methods add_socket and remove_socket can be used if
    another part or your code have opened sockets, and you want
    Network to select on them.
    """

    __slots__ = ('sockets', 'filenos')

    def __init__(self):
        self.sockets = []
        self.filenos = {}

    def listen(self, addr, port, on_read):
        """
        Listen for TCP connections on addr:port.
        The callback on_read is called, with the socket as single parameter,
        when data is available.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.add_socket(sock, lambda s: self.accept(s, on_read))
        sock.bind((addr, port))
        sock.listen(1)

    def accept(self, sock, on_read):
        """
        Used internally to accept a connection on a socket.
        But if you need, you can use it, it will do a soc.accept()
        then add the accepted sock to the list of monitored ones, so
        when data is available, the callback on_read will be called.
        """
        logging.debug("Accepting a connection")
        conn, _ = sock.accept()
        self.add_socket(conn, on_read)

    def add_socket(self, sock, on_read=None, on_write=None):
        """
        Manually add a socket and its on_read / on_write handlers
        to this Network.
        """
        logging.debug("Adding socket %d", sock.fileno())
        self.sockets.append(sock)
        self.filenos[sock.fileno()] = Socket(sock, on_read, on_write)

    def remove_socket(self, sock):
        """
        Manually remove a socket from the list of monitored ones.
        """
        logging.debug("Removing socket %d", sock.fileno())
        self.sockets.remove(sock)
        del self.filenos[sock.fileno()]

    def run_forever(self):
        """
        Start the infinite loop listening on network.
        """
        while True:
            logging.debug("Entering select...")
            (can_read, _, _) = select.select(self.sockets, [], [])
            [self.filenos[sock.fileno()].on_read(sock) for sock in can_read]


class IRCBot:
    """
    IRCBot is a basic bot that connect to a given serveur and channel with
    a given nickname, and then, only tries to execute 'executables' in the
    hooks directory named after the kinds of event it receive that
    can be :
     * error
     * join
     * kick
     * mode
     * part
     * ping
     * privmsg
     * privnotice
     * pubmsg <- Most usefull, it receive messages of the channel
     * pubnotice
     * quit
     * invite
     * pong
    and a generic hook called for EVERY event, even if a hook exists for the
    named event :
     * all_raw_messages

    """
    def __init__(self, server, chan, key, nickname, local_port):
        self.network = Network()
        self.chan = chan
        self.key = key
        self.ircobj = IRC(self.add_socket, self.rm_socket)
        self.connection = self.ircobj.server()
        self.ircobj.add_global_handler("all_events", self._dispatcher, -10)
        self.connection.connect(server, 6667, nickname)
        self.network.listen("127.0.0.1", local_port, self.read_message)
        self.network.run_forever()

    def read_message(self, sock):
        """
        Read a message on the local socket and write it to the channel
        """
        data = sock.recv(1024)
        if not data:
            self.network.remove_socket(sock)
        else:
            self.write_message(data)

    def write_message(self, message):
        """
        Write a message to the channel
        """
        if len(message) > 0:
            for line in message.split('\n'):
                wrapped = wrap(line, 512 - len("\r\n") -
                               len("PRIVMSG %s :" % self.chan))
                for wrapped_line in wrapped:
                    if len(wrapped_line.strip()) > 0:
                        self.connection.privmsg(self.chan, wrapped_line)
                        sleep(1)

    def add_socket(self, sock):
        self.network.add_socket(sock, lambda s: self.ircobj.process_data([s]))

    def rm_socket(self, sock):
        self.network.remove_socket(sock)

    def _dispatcher(self, _, event):
        if event.eventtype() == 'endofmotd':
            logging.info("Joining channel %s", self.chan)
            self.connection.join(self.chan, self.key)
        try:
            source = event.source().split('!', 1) \
                if event.source() is not None else []
            source_login = source[0] if len(source) > 0 else ""
            source_hostname = source[1] if len(source) > 1 else ""
            target = event.target().split('!', 1) \
                if event.target() is not None else []
            target_login = target[0] if len(target) > 0 else ""
            target_hostname = target[1] if len(target) > 1 else ""
            call = ['hooks-enabled/%s' % event.eventtype(), source_login,
                    source_hostname, target_login, target_hostname]
            call.extend(event.arguments())
            logging.info("calling: %s", str(call))
            if os.path.isfile(call[0]):
                output = subprocess.Popen(call, stdout=subprocess.PIPE)\
                    .communicate()
                if output[1] is not None:
                    logging.info("    \_'%s'", output[1])
                self.write_message(output[0])
        except Exception, ex:
            logging.critical(ex)


def connect_to_irc(conf):
    if conf.daemonize:
        import daemon
        with daemon.DaemonContext():
            IRCBot(conf.server, conf.chan, conf.key, conf.nickname,
                   conf.local_port)
    else:
        IRCBot(conf.server, conf.chan, conf.key, conf.nickname,
               conf.local_port)


def netwrite(to_send, host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.connect((host, port))
        [sock.send(data) for data in to_send]


def say_something(conf):
    if len(conf.message) == 1 and conf.message[0] == '-':
        netwrite(sys.stdin, '127.0.0.1', conf.local_port)
    else:
        netwrite([' '.join(conf.message)], '127.0.0.1', conf.local_port)

HELP = {
"server": "IRC server address (ip or dns name)",
"chan": "Chan to join",
"nickname": "Nickname to use",
"local_port": "Local port to listen to messages",
"say_local_port": "Local listening port of the bot",
"verbose": "Be verbose (Show warning messazges)",
"vverbose": "Be very verbose (Show info messazges)",
"vvverbose": "Be very very verbose (Show debug messages)",
"quiet": "Be quiet",
"ircbot": "IRC Bot",
"connect": "Connect to a server",
"say": "Say something (once connected)",
"message": "What to say, '-' means stdin",
"daemonize": "Demonize the client process",
"key": "Channel key"}


def main():
    parser = argparse.ArgumentParser(description=HELP['ircbot'])
    parser.add_argument('-v', '--show-warnings',
                        dest='logging_level',
                        action='store_const',
                        const=logging.WARNING,
                        help=HELP['verbose'])
    parser.add_argument('-vv', '--show-infos',
                        dest='logging_level',
                        action='store_const',
                        const=logging.INFO,
                        help=HELP['vverbose'])
    parser.add_argument('-vvv', '--show-debugs',
                        dest='logging_level',
                        action='store_const',
                        const=logging.DEBUG,
                        help=HELP['vvverbose'])
    parser.add_argument('-q', '--quiet',
                        dest='logging_level',
                        action='store_const',
                        const=logging.CRITICAL,
                        help=HELP['quiet'])

    subparsers = parser.add_subparsers()
    parser_client = subparsers.add_parser('connect', help=HELP['connect'])
    parser_client.add_argument('server', help=HELP['server'])
    parser_client.add_argument('chan', help=HELP['chan'])
    parser_client.add_argument('nickname', help=HELP['nickname'])
    parser_client.add_argument('-p', '--port',
                               dest="local_port",
                               help=HELP['local_port'],
                               type=int,
                               default=6668)
    parser_client.add_argument('-d', '--daemonize',
                               action='store_true',
                               dest='daemonize',
                               help=HELP['daemonize'])
    parser_client.add_argument('-k', '--key',
                               dest='key',
                               help=HELP['key'],
                               default='')
    parser_client.set_defaults(func=connect_to_irc)
    parser_say = subparsers.add_parser('say', help=HELP['say'])
    parser_say.add_argument('message',
                            nargs='+',
                            help=HELP['message'])
    parser_say.add_argument('-p', '--port',
                            dest="local_port",
                            help=HELP['say_local_port'],
                            type=int,
                            default=6668)
    parser_say.set_defaults(func=say_something)
    conf = parser.parse_args()
    logging.basicConfig(level=conf.logging_level,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    conf.func(conf)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
