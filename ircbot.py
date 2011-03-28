#!/usr/bin/env python
import logging
import socket
import argparse
import select
import sys
import os
import subprocess
from pipe import netwrite
from irclib import IRC
from time import sleep

class Socket():
    def __init__(self, socket, on_read=None, on_write=None):
        self.socket = socket
        if on_read:
            self.on_read = on_read
        if on_write:
            self.on_write = on_write

    def on_write(self, socket):
        pass

    def on_read(self, socket):
        pass

class Network:
    def __init__(self):
        self.sockets = []
        self.sockets_by_fileno = {}

    def listen(self, addr, port, on_read):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.add_socket(sock, lambda s: self.accept(s, on_read))
        sock.bind((addr, port))
        sock.listen(1)

    def accept(self, socket, on_read):
        logging.debug("Accepting a connection")
        conn, addr = socket.accept()
        self.add_socket(conn, on_read)

    def add_socket(self, socket, on_read=None, on_write=None):
        logging.debug("Adding socket %d" % socket.fileno())
        self.sockets.append(socket)
        self.sockets_by_fileno[socket.fileno()] = Socket(socket, on_read, on_write)

    def remove_socket(self, socket):
        logging.debug("Removing socket %d" % socket.fileno())
        self.sockets.remove(socket)
        del self.sockets_by_fileno[socket.fileno()]

    def run_forever(self):
        while True:
            logging.debug("Entering select...")
            (r, w, e) = select.select(self.sockets, [], [])
            for have_to_read in r:
                logging.debug("Socket %d have something to read" % have_to_read.fileno())
                self.sockets_by_fileno[have_to_read.fileno()].on_read(have_to_read)

class IRCBot:
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

    def read_message(self, socket):
        data = socket.recv(1024)
        if not data:
            self.network.remove_socket(socket)
        else:
            self.connection.privmsg(self.chan, data)

    def add_socket(self, socket):
        self.network.add_socket(socket, lambda s: self.ircobj.process_data([s]))

    def rm_socket(self, socket):
        self.network.remove_socket(socket)

    def _dispatcher(self, c, e):
        if e.eventtype() == 'endofmotd':
            logging.info("Joining channel %s" % self.chan)
            self.connection.join(self.chan, self.key)
        try:
            source = e.source().split('!', 1) if e.source() is not None else []
            source_login = source[0] if len(source) > 0 else ""
            source_hostname = source[1] if len(source) > 1 else ""
            target = e.target().split('!', 1) if e.target() is not None else []
            target_login = target[0] if len(target) > 0 else ""
            target_hostname = target[1] if len(target) > 1 else ""
            call = ['hooks/%s' % e.eventtype(), source_login, source_hostname,
                    target_login, target_hostname]
            call.extend(e.arguments())
            logging.info("calling: %s" % str(call))
            if os.path.isfile(call[0]):
                output = subprocess.Popen(call, stdout=subprocess.PIPE).communicate()
                if output[1] is not None:
                    logging.info("    \_'%s'" % output[1])
                if len(output[0]) > 0:
                    for line in output[0].split('\n'):
                        if len(line.strip()) > 0:
                            self.connection.privmsg(self.chan, line)
                            sleep(1)
        except Exception, ex:
            logging.critical(ex)

def connect_to_irc(conf):
    if conf.daemonize:
        import daemon
        with daemon.DaemonContext():
            IRCBot(conf.server, conf.chan, conf.key, conf.nickname, conf.local_port)
    else:
        IRCBot(conf.server, conf.chan, conf.key, conf.nickname, conf.local_port)

def say_something(conf):
    if len(conf.message) == 1 and conf.message[0] == '-':
        sys.stdin | netwrite('127.0.0.1', conf.local_port)
    else:
        [' '.join(conf.message)] | netwrite('127.0.0.1', conf.local_port)

help_server = "IRC server address (ip or dns name)"
help_chan = "Chan to join"
help_nickname = "Nickname to use"
help_local_port = "Local port to listen to messages"
help_say_local_port = "Local listening port of the bot"
help_verbose = "Be verbose (Show warning messazges)"
help_vverbose = "Be very verbose (Show info messazges)"
help_vvverbose = "Be very very verbose (Show debug messages)"
help_quiet = "Be quiet"
help_ircbot = "IRC Bot"
help_connect = "Connect to a server"
help_say = "Say something (once connected)"
help_message = "What to say, '-' means stdin"
help_daemonize = "Demonize the client process"
help_key = "Channel key"

def main():
    parser = argparse.ArgumentParser(description=help_ircbot)
    parser.add_argument('-v', '--show-warnings',
                        dest='logging_level',
                        action='store_const',
                        const=logging.WARNING,
                        help=help_verbose)
    parser.add_argument('-vv', '--show-infos',
                        dest='logging_level',
                        action='store_const',
                        const=logging.INFO,
                        help=help_vverbose)
    parser.add_argument('-vvv', '--show-debugs',
                        dest='logging_level',
                        action='store_const',
                        const=logging.DEBUG,
                        help=help_vvverbose)
    parser.add_argument('-q', '--quiet',
                        dest='logging_level',
                        action='store_const',
                        const=logging.CRITICAL,
                        help=help_quiet)

    subparsers = parser.add_subparsers()
    parser_client = subparsers.add_parser('connect', help=help_connect)
    parser_client.add_argument('server', help=help_server)
    parser_client.add_argument('chan', help=help_chan)
    parser_client.add_argument('nickname', help=help_nickname)
    parser_client.add_argument('-p', '--port',
                               dest="local_port",
                               help=help_local_port,
                               type=int,
                               default=6668)
    parser_client.add_argument('-d', '--daemonize',
                               action='store_true',
                               dest='daemonize',
                               help=help_daemonize)
    parser_client.add_argument('-k', '--key',
                               dest='key',
                               help=help_key,
                               default='')
    parser_client.set_defaults(func=connect_to_irc)
    parser_say = subparsers.add_parser('say', help=help_say)
    parser_say.add_argument('message',
                            nargs='+',
                            help=help_message)
    parser_say.add_argument('-p', '--port',
                            dest="local_port",
                            help=help_say_local_port,
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

