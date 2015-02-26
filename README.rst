==========
imapcmdtun
==========

Tunnel and authenticate IMAP and SMTP connections from a local socket
directly to a remote pre-authenticated command.

Allows using IMAP and SMTP clients requiring socket access (for example
Thunderbird) with remote mailboxes that are not accessible by direct
connections to IMAP and SMTP sockets or ones that use authentication methods
which are not supported by the mail client.

`imapcmdtun` runs basic login (username, password) authentication on its
local IMAP socket and after authentication hooks the local socket to a
(possibly) remote pre-authenticated imap command.  The local SMTP
connections are not authenticated at the moment; they're just passed as-is
to the remote sendmail or other configured command.


Usage
=====

::

    python imapcmdtun.py config=config.json

config.json being something like::

    [
        {
            "protocol": "imap",
            "port": 9993,
            "username": "os",
            "password": "abcd",
            "ssh_target": "user@mail.example.com"
        },
        {
            "protocol": "smtp",
            "port": 9925,
            "ssh_target": "user@mail.example.com"
        }
    ]

`username` and `password` are used to authenticate the client on the local
socket which is bound to `port`.  `ssh_target` is the first argument for ssh
to connect to a remote host for accessing an IMAP mailbox or SMTP relay.
`imapcmdtun` executes dovecot's imap service by default for IMAP connections
and `sendmail -bs` for smtp commands, but the commands can be overridden
using the `imap_command` and `smtp_command` configuration keys.

Configuration options for a single service can also be passed to
`imapcmdtun` directly on the commandline as arguments in the format
`key=value` instead of using a JSON configuration file.

License
=======

imapcmdtun is released under the Apache License, Version 2.0.

For the exact license terms, see `LICENSE` and
http://opensource.org/licenses/Apache-2.0 .

Contact
=======

imapcmdtun was created and is maintained by Oskari Saarenmaa <os@ohmu.fi>.

Bug reports and patches are very welcome, please post them as GitHub issues
and pull requests at https://github.com/saaros/imapcmdtun
