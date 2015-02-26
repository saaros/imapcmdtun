# imapcmdtun - tunnel imap connections from socket to a command
#
# Copyright (c) 2015, Oskari Saarenmaa <os@ohmu.fi>
#
# This file is under the Apache License, Version 2.0.
# See the file `LICENSE` for details.

import errno
import json
import logging
import os
import select
import socket
import sys


def main(args):
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s\t%(levelname)s\t%(name)s[%(process)s]\t%(message)s")
    services = []
    config = {}
    for arg in args:
        k, _, v = arg.partition("=")
        if k == "config":
            with open(v, "r") as f:
                services.extend(json.load(f))
        else:
            if k == "port":
                v = int(v)
            config[k] = v
    if config:
        services.append(config)
    listener(services)


def listener(services):
    log = logging.getLogger("imapcmdtun")

    socks = {}
    for config in services:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", config["port"]))
        sock.listen(1)
        log.info("listening on port %r (%s)", config["port"], config["protocol"])
        socks[sock] = config

    while True:
        rlist, _, _ = select.select(socks, [], [])
        for lsock in rlist:
            config = socks[lsock]
            res = lsock.accept()
            log.info("new %s connection from %r", config["protocol"], res[1])
            sock = res[0]
            pid = os.fork()
            if pid == 0:
                for lsock in socks:
                    lsock.close()
                if config["protocol"] == "imap":
                    return imap_client(config, log, sock)
                elif config["protocol"] == "smtp":
                    return smtp_client(config, log, sock)
                else:
                    raise Exception("unknown protocol")
            sock.close()
        # reap children
        while pid:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except OSError as ex:
                if ex.errno == errno.ECHILD:
                    break
            if pid:
                log.info("child %r exited with status %r", pid, status)


def smtp_client(config, log, s):
    tunnel_command = config.get("tunnel_command")
    if not tunnel_command:
        ssh_target = config["ssh_target"]
        imap_command = config.get("smtp_command")
        if not imap_command:
            imap_command = "/usr/sbin/sendmail -bs"
        tunnel_command = ["/usr/bin/ssh", ssh_target, imap_command]
    log.info("Executing %r", tunnel_command)
    os.close(0)
    os.close(1)
    os.close(2)
    os.dup2(s.fileno(), 0)
    os.dup2(s.fileno(), 1)
    os.close(s.fileno())
    os.execv(tunnel_command[0], tunnel_command)


def imap_client(config, log, s):
    def output(m):
        log.info("%r>>>%r", s.fileno(), m)
        s.send(m if isinstance(m, bytes) else m.encode("utf-8"))

    tunnel_command = config.get("tunnel_command")
    if not tunnel_command:
        ssh_target = config["ssh_target"]
        imap_command = config.get("imap_command")
        if not imap_command:
            imap_command = "IMAPLOGINTAG={tag} doveconf -f service=imap -m imap -e /usr/libexec/dovecot/imap"
        tunnel_command = ["/usr/bin/ssh", ssh_target, imap_command]

    capabilities = "CAPABILITY IMAP4rev1 LITERAL+ LOGIN-REFERRALS ID ENABLE IDLE"
    output("* OK [{0}] imapcmdtun ready.\r\n".format(capabilities))

    buf = ""
    while True:
        try:
            data = s.recv(4096)
        except socket.error as ex:
            if ex[0] in (errno.EAGAIN, errno.EINTR):
                continue
            log.exception("socket.error")
            return

        if not data:
            log.info("no data, DONE")
            break
        if isinstance(data, bytes) and bytes is not str:
            data = data.decode("utf-8")
        buf += data
        log.info("%r<<<read %r chars, buffer now %r chars",
                 s.fileno(), len(data), len(buf))

        while True:
            msgstr, crln, rest = buf.partition("\r\n")
            if crln != "\r\n":
                log.info("no command in buffer, waiting")
                break
            buf = rest
            msg = msgstr.split()
            try:
                if len(msg) < 2:
                    output("{0} BAD missing command\r\n".format(msg[0] if msg else "*"))
                    continue
                tag = msg[0]
                cmd = msg[1].upper()
                if cmd == "LOGIN" and len(msg) >= 4:
                    log_msg = list(msg)
                    log_msg[3] = "***"
                else:
                    log_msg = msg
                log.info("COMMAND: %r", log_msg)
                if cmd == "CAPABILITY":
                    output("* {0}\r\n".format(capabilities))
                    output("{0} OK {1} completed.\r\n".format(tag, cmd))
                elif cmd == "LOGOUT":
                    output("* BYE moido\r\n")
                    output("{0} OK {1} completed.\r\n".format(tag, cmd))
                    return
                elif cmd == "LOGIN" and len(msg) == 4:
                    username = msg[2].strip('"')
                    password = msg[3].strip('"')
                    if username != config["username"] or password != config["password"]:
                        output("{0} NO [AUTHENTICATIONFAILED] Authentication failed.".format(tag))
                        return
                    tunnel_command_formatted = [arg.format(tag=tag) for arg in tunnel_command]
                    log.info("Executing %r", tunnel_command_formatted)
                    os.close(0)
                    os.close(1)
                    os.close(2)
                    os.dup2(s.fileno(), 0)
                    os.dup2(s.fileno(), 1)
                    os.close(s.fileno())
                    os.execv(tunnel_command[0], tunnel_command_formatted)
                else:
                    output("{0} BAD unknonwn command {1}\r\n".format(tag, cmd))
            except socket.error as ex:
                log.exception("socket.error")
                return


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
