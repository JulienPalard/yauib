Yet Another Useless IRC Bot

![Yauib Logo](https://mdk.fr/yauib_logo.png)


# Introduction

This bot is designed to be simple for developers.


# Dependencies

There's only two dependencies, `irclib` and `argparse`:

- On debian, `aptitude install python-irclib python-arparse`
- Or `pip install python-irclib python-argparse`.


# Simple Quick Start

Here is a simple quick start using my simple hooks, so you don't have
to write code.

Fetch it:

    $ git clone git://github.com/JulienPalard/yauib.git && cd yauib

Launch it:

    $ ./ircbot.py connect 'irc.server.example.com' '#your_channel' 'your_bot_login'
    Now your bot should appear on your channel.

Remove the hook that say that you haven't read the README file:

    $ rm -f hooks-enabled/pubmsg

Select one basic hook:

    Now it's the time to hook some events, let's bind the 'command' hook to
    public messages :
    $ ( cd hooks-enabled && ln -s ../hooks-available/command pubmsg )

    The 'command' hook tries to call executables in the directory
    'commands-enabled' for everything said on the channel, with the first word
    as executable name, and other as arguments, so the next step is to choose
    some commands.

Select some basic commands

    Let's test them all ... you'll choose later :X
    $ ( cd commands-enabled && for command in ../commands-available/*; do ln -s "$command"; done )
    /!\ Some commands will need writable directories like 'logs', 'db' or 'conf'

Now try your bot writing 'say hello' on the channel :

     The bot will run 'hooks-enabled/pubmsg' that points to
     'hooks-available/command'. hooks-available/commands receiving 'say
     hello' will call `commands-enabled/say hello`. say is, basically a
     shell script with 'echo $*' So it will echo hello, that will be
     wrote back by the bot on the channel.


# I wanna write commands, how it works ?

If you don't want to write complicated hooks, just use my simple one,
and write commands.

You first have to bind the `command` hook to `pubmsg` and `privmsg` hooks:

    $ ( cd hooks-enabled && ln -s ../hooks-available/command pubmsg )
    $ ( cd hooks-enabled && ln -s ../hooks-available/command privmsg )

Now, for each received message, my 'command' hook will try to find an
executable in the 'advanced-commands-enabled' directory, then in the
`commands-enabled` directory, finally trying to run
`commands-enabled/run`.

So you can write commands in any language you want, just make them
read their arguments, and make them write to stdout.  A command also
can put debugging information on stderr, the information will be
logged by the bot, you can run the bot with the -vvv option to get
your debug back to the screen.

As commands are only executables, you don't have to restart the bot to
make it see them, just add the file, and bim, it works.


## Advanced commands

Advanced commands have to live in ./advanced-commands-available/
directory, create a symbolink link in the ./advanced-commands-enabled/
to make them callable for the 'command' hook, permitting you to
enable/disable a command in a few seconds.

Commands in the advanced-commands-enabled permits you to return raw
messages directly to the IRC server, permitting you to send messages,
kicks, bans, join, whatever you want, you have to understand the IRC
protocol to use them.


## Basic commands

Basic commands have to live in ./commands-available/
directory, create a symbolink link in the ./commands-enabled/
to make them callable for the 'command' hook, permitting you to
enable/disable a command in a few seconds.

A basic command can only reply with text, so don't worry about IRC
protocol, don't worry about multiline responses, don't worry about
response length limit, just write something to stdout it will be sent
back to the one who called the command.

A basic command writing a calendar on the channel should be named cal,
and only contain:

    #!/bin/sh
    cal

# I wanna write hooks, how it works ?

YAUIB is a very basic bot that, for each event received from IRC will
call a hook in the directory ./hooks-enabled/, so write your own
hooks, in every language you want.


## Hooks protocol

Hooks reply can have two forms:

 * Form 1: Prefix your response by 'RAW ' and every following lines
   will be sent to the server.

 * Form 2: Prefix your response by 'MSG ', put a target (typically
   argv[3] if you wanna reply), and your response. Responses from MSG
   can follow on multiples lines, each line will be sent to the
   server, delayed from 1 second, to avoid being kiked too early for
   flood, your response will also be splitted in multiples lines if
   it's too long, so just don't worry when using this form.


## On which hooks can I hook my scripts ?

Typical usefull commands are:

- `all_raw_messages`: Get all messages from IRC server, do whatever you want.
    Specific parameters: Only the full message, in one parameter
- `pubmsg`: Hook on public messages
    Specific parameters: Only the sentence, in one parameter
- `privmsg`: Hook on private messages
    Specific parameters: Only the sentence, in one parameter

There are tons of other hooks ( > 100 ) from irclib and I didn't know
them all so watch your logs to catch those you want. (And document
their parameters here ?)

## Which parameters are sent to hooks ?

Parameter 1, 2, 3 and 4 are:
source login, source host, target login, and target host
followed by command-specific parameters.

There is a directory to store every hooks, that is hooks-available so you
should enable only some needed, creating symlinks in the directory
hooks-enabled.

There is a usefull default hook I wrote for you, it's named 'command'.
It executes commands that it find in the directory commands-enabled
so you have to create some symlinks from the directory commands-available
where I stored the commands I wrote.

NOTE: You don't have to restart the bot when you change / add a hook.

So a very basic 'parrot' hook should be:

    #!/bin/sh
    shift 4 # Drop sender login and host, target login and host
    printf "%s\n" "$*"


# Is there another way to make the bot speak ?

Yes, the bot is listening on a local port, by default 6668.
Everything received on this port is wrote back to the channel.
So a simple:

    $ echo foo | netcat localhost 6668

will do the trick, but you should also try:

    # ./ircbot.py say foo

That does the same!

With this feature you can push messages from cron, webpages or
everything else.

# Conclusion

Enjoy creating new hooks / commands, using your favorite language!

> logo by @Abdur-rahmaanj
