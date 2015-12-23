# Copyright (c) 2010-2015 Bo Lin
# Copyright (c) 2010-2015 Yanhong Annie Liu
# Copyright (c) 2010-2015 Stony Brook University
# Copyright (c) 2010-2015 The Research Foundation of SUNY
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import io
import sys
import pickle
import random
import select
import socket
import logging
import ipaddress
import threading

from collections import namedtuple

log = logging.getLogger("Endpoint")

INTEGER_BYTES = 8

class Connection:
    """Represents a connection to a remote peer.

    """
    def __init__(self, sock, addr, proto):
        self.sock = sock
        self.peer = addr
        self.proto = proto

    def fileno(self):
        return self.sock.fileno()

    def close(self):
        self.sock.close()

class PendingConnection:
    """Placeholder for a TCP socket before full protocol negotiation completes.

    """
    def __init__(self, sock, addr, proto):
        super().__init__(sock, addr, proto)


class Protocol:
    """Defines a lower level transport protocol.

    """
    max_retries = 5
    min_port = 10000
    max_port = 65535

    def __init__(self, endpoint, port=None):
        self._ep = endpoint
        self.port = port

        self._log = logging.getLogger(self.__class__.__name__)

    def start(self):
        """Starts the protocol.

        For wrapper protocols this creates and binds the lower level sockets.

        """
        pass

    def send(self, msg, conn=None):
        """Send `msg' through `conn'.

        Returns `True' if send succeeded, `False' otherwise.

        """
        return False

    def recv(self, conn):
        """Receives a message on `conn'.

        """
        return None

class TcpProtocol(Protocol):
    def __init__(self, endpoint, port=None):
        super().__init__(endpoint, port)

    def start(self):
        """Starts the TCP listener socket.

        """

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.port is None:
            done = False
            for _ in range(Protocol.max_retries):
                self.port = random.randint(Protocol.min_port, Protocol.max_port)
                try:
                    self.listener.bind((self._ep.hostname, self.port))
                    done = True
                    break
                except socket.error:
                    pass
            if not done:
                self.listener.close()
                raise socket.error("Unable to bind to free port.")
        else:
            self.listener.bind((self._ep.hostname, self.port))

    def _accept(self):
        sock, addr = self.listener.accept()
        conn = PendingConnection(sock, addr, self)
        self._ep.register(conn)

    def recv(self, conn):
        """Handles incoming data over `conn'."""

        if conn.sock is self.listener:
            self._accept()
        else:
            try:
                bytedata = self._receive_1(INTEGER_BYTES, conn.sock)
                datalen = int.from_bytes(bytedata, sys.byteorder)
                bytedata = self._receive_1(datalen, conn.sock)
                if isinstance(conn, PendingConnection):
                    peerid, tstamp, data = pickle.loads(bytedata)
                    bytedata = None
                    newconn = Connection(conn.sock, peerid, self)
                    self._ep.replate(conn, newconn)
                    yield (peerid, tstamp, data)
                else:
                    tstamp, data = pickle.loads(bytedata)
                    bytedata = None
                    yield (conn.peer, tstamp, data)

            except pickle.UnpicklingError as e:
                self._log.warn("UnpicklingError, packet from %s dropped",
                               TcpEndPoint.receivers[c])
            except socket.error as e:
                self._log.debug("Remote connection %s terminated.",
                                str(c))
                self._ep.deregister(conn)

    def _receive_1(self, totallen, conn):
        """Helper function to receive `totallen' number of bytes over
        `conn'. 

        """
        msg = bytearray(totallen)
        offset = 0
        while offset < totallen:
            recvd = conn.recv_into(memoryview(msg)[offset:])
            if recvd == 0:
                raise socket.error("EOF received")
            offset += recvd
        return msg

    def send(self, data, dest, timestamp=0):
        """Sends `data' to `dest'. """
        retry = 1
        buffer = io.BytesIO(b'0' * INTEGER_BYTES)
        for _ in range(Protocol.max_retries):
            conn = self._ep.get_connection(dest)
            if conn is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.connect(self._ep.decode(dest, self))
                except socket.error:
                    self._log.debug("Can not connect to %s. Peer is down.",
                                   str(self._address))
                    return False
                conn = Connection(sock, dest, self)
                self._ep.register(conn)
                bytedata = pickle.dumps((self._ep.pid, timestamp, data))
            else:
                bytedata = pickle.dumps((timestamp, data))

            l = len(bytedata)
            header = int(l).to_bytes(INTEGER_BYTES, sys.byteorder)
            mesg = header + bytedata

            if len(mesg) > MAX_TCP_BUFSIZE:
                self._log.warn("Packet size exceeded maximum buffer size! "
                               "Outgoing packet dropped.")
                self._log.debug("Dropped packet: %s",
                                str((src, timestamp, data)))
                return False

            else:
                try:
                    conn.sendall(mesg)
                    self._log.debug("Sent packet %r to %r." % (data, self))
                    return True
                except socket.error as e:
                    pass
                self._log.debug("Error sending packet, retrying.")
                retry += 1
                if retry > MAX_RETRY:
                    self._log.debug("Max send retry count reached, "
                                    "attempting to reconnecting...")
                    conn.close()
                    self._ep.deregister(conn, self)
                    retry = 1

        return False

class ProtocolSuite:
    """A bundle of network protocols.

    Each process in the same instance of distributed program must have the
    same ProtocolSuite.
    """
    def __init__(self, endpoint):
        self._ep = endpoint
        self.protocols = []

    def start(self):
        pass

class TcpUdpSuite(ProtocolSuite):
    def __init__(self, endpoint):
        super().__init__(endpoint)
        self.tcpproto = None
        self.udpproto = None

    def start(self):
        self.tcpproto = TcpProtocol(self._ep)
        self.udpproto = UdpProtocol(self._ep)
        tcpport = tcp.start(self)
        udpport = udp.start(self)

    # TODO: We use a namedtuple for simplicity, but needs to be changed if we
    # are to support process migration:
    class ProcessId(namedtuple('ProcessId',
                               'udpport, tcpport, nodeport, ipaddr')):
        """Object representing a process id.

        """
        @property
        def tcp_addr(self):
            ipaddr = ipaddress.ip_address(self.ipaddr)
            return (str(ipaddr), self.tcpport)

        @property
        def udp_addr(self):
            ipaddr = ipaddress.ip_address(self.ipaddr)
            return (str(ipaddr), self.udpport)


class EndPoint:
    """Manages all communication channels for the current process.

    """
    def __init__(self, name=None, proctype=None):
        if name is None:
            self._name = 'localhost'
        else:
            self._name = name
        self._proc = None
        self._proctype = proctype
        self._log = logging.getLogger("runtime.EndPoint")
        self._address = None
        self._connections = None
        self._lock = None

    def _init_config(self):
        from . import common
        opts = common.global_options()
        Protocol.max_retries = opts.max_retries
        Protocol.min_port = opts.min_port
        Protocol.max_port = opts.max_port
        self._connections = LRU(opts.max_connections)
        self.host = socket.gethostbyname(self._name)

    def start(self):
        try:
            # 1. initialize configuration variables and lock object. We need
            # to init config here in order to support the `spawn' start
            # method
            self._init_config()
            self._lock = threading.RLock()
            # 2. start the protocols:
            return True
        except socket.error as e:
            self._log.error("Unable to start endpoint: ", e)
            return False

    def register(self, conn):
        """Adds `conn' to list of connections."""
        with self._lock:
            self._connections[conn.peer] = conn

    def replace(self, conn, newconn):
        """Replace `conn' with `newconn'."""
        with self._lock:
            del self._connections[conn.peer]
            self._connections[newconn.peer] = newconn

    def get_connection(self, pid):
        with self._lock:
            if pid in self._connections:
                return self._connections[pid]
            else:
                return None

    def deregister(self, conn):
        """Removes `conn' from list of connections."""
        with self._lock:
            del self._connections[conn.peer]

    def send(self, data, target, timestamp = 0):
        pass

    def recv(self, block, timeout = None):
        pass

    def getlogname(self):
        if self._address is not None:
            return "%s_%s" % (self._address[0], str(self._address[1]))
        else:
            return self._name

    def close(self):
        pass

    def __str__(self):
        if self._address is not None:
            return str(self._address)
        else:
            return self._name

    def __repr__(self):
        if self._proctype is not None:
            return "<" + self._proctype.__name__ + str(self) + ">"
        else:
            return "<process " + str(self) + ">"


# TCP Implementation:

MAX_TCP_CONN = 200
MIN_TCP_PORT = 10000
MAX_TCP_PORT = 40000
MAX_UDP_BUFSIZE = 20000
MAX_TCP_BUFSIZE = 200000          # Maximum pickled message size
MAX_RETRY = 5

class TcpEndPoint(EndPoint):
    """Endpoint based on TCP.

    """

    senders = None
    receivers = None

    def __init__(self, name=None, proctype=None, port=None):
        super().__init__(name, proctype)

        TcpEndPoint.receivers = dict()
        TcpEndPoint.senders = LRU(MAX_TCP_CONN)

        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if port is None:
            while True:
                self._address = (self._name,
                                 random.randint(MIN_TCP_PORT, MAX_TCP_PORT))
                try:
                    self._conn.bind(self._address)
                    break
                except socket.error:
                    pass
        else:
            self._address = (self._name, port)
            self._conn.bind(self._address)

        self._conn.listen(10)
        TcpEndPoint.receivers[self._conn] = self._address

        self._log = logging.getLogger("runtime.TcpEndPoint(%s)" %
                                      super().getlogname())
        self._log.debug("TcpEndPoint %s initialization complete",
                        str(self._address))

    def send(self, data, src, timestamp = 0):
        retry = 1
        while True:
            conn = TcpEndPoint.senders.get(self)
            if conn is None:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    conn.connect(self._address)
                    TcpEndPoint.senders[self] = conn
                except socket.error:
                    self._log.debug("Can not connect to %s. Peer is down.",
                                   str(self._address))
                    return False

            bytedata = pickle.dumps((src, timestamp, data))
            l = len(bytedata)
            header = int(l).to_bytes(INTEGER_BYTES, sys.byteorder)
            mesg = header + bytedata

            if len(mesg) > MAX_TCP_BUFSIZE:
                self._log.warn("Packet size exceeded maximum buffer size! "
                               "Outgoing packet dropped.")
                self._log.debug("Dropped packet: %s",
                                str((src, timestamp, data)))
                break

            else:
                try:
                    if self._send_1(mesg, conn):
                        break
                except socket.error as e:
                    pass
                self._log.debug("Error sending packet, retrying.")
                retry += 1
                if retry > MAX_RETRY:
                    self._log.debug("Max retry count reached, reconnecting.")
                    conn.close()
                    del TcpEndPoint.senders[self]
                    retry = 1

        self._log.debug("Sent packet %r to %r." % (data, self))
        return True

    def _send_1(self, data, conn):
        msglen = len(data)
        totalsent = 0
        while totalsent < msglen:
            sent = conn.send(data[totalsent:])
            if sent == 0:
                return False
            totalsent += sent
        return True

    def recvmesgs(self):
        try:
            while True:
                r, _, _ = select.select(TcpEndPoint.receivers.keys(), [], [])

                if self._conn in r:
                    # We have pending new connections, handle the first in
                    # line. If there are any more they will have to wait until
                    # the next iteration
                    conn, addr = self._conn.accept()
                    TcpEndPoint.receivers[conn] = addr
                    r.remove(self._conn)

                for c in r:
                    try:
                        bytedata = self._receive_1(INTEGER_BYTES, c)
                        datalen = int.from_bytes(bytedata, sys.byteorder)

                        bytedata = self._receive_1(datalen, c)
                        src, tstamp, data = pickle.loads(bytedata)
                        bytedata = None

                        if not isinstance(src, EndPoint):
                            raise TypeError()
                        else:
                            yield (src, tstamp, data)

                    except pickle.UnpicklingError as e:
                        self._log.warn("UnpicklingError, packet from %s dropped",
                                       TcpEndPoint.receivers[c])

                    except socket.error as e:
                        self._log.debug("Remote connection %s terminated.",
                                        str(c))
                        del TcpEndPoint.receivers[c]

        except select.error as e:
            self._log.debug("select.error occured, terminating receive loop.")

    def _receive_1(self, totallen, conn):
        msg = bytes()
        while len(msg) < totallen:
            chunk = conn.recv(totallen-len(msg))
            if len(chunk) == 0:
                raise socket.error("EOF received")
            msg += chunk
        return msg

    def close(self):
        pass

    def _udp_init(self, name=None, proctype=None, port=None):
        self._udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if port is None:
            while True:
                self._address = (self._name,
                                 random.randint(MIN_UDP_PORT, MAX_UDP_PORT))
                try:
                    self._udpsock.bind(self._address)
                    break
                except socket.error:
                    pass
        else:
            self._address = (self._name, port)
            self._udpsock.bind(self._address)

        log.debug("UdpEndPoint %s initialization complete", str(self._address))

    def send(self, data, tgt, timestamp = 0):
        bytedata = pickle.dumps((self._pid, timestamp, data))
        if len(bytedata) > MAX_UDP_BUFSIZE:
            log.warn("Data size exceeded maximum buffer size! "
                     "Outgoing packet dropped.")
            log.debug("Dropped packet: %s", str(bytedata))

        elif (self._udpsock.sendto(bytedata, self._address) !=
              len(bytedata)):
            raise socket.error()

    def recvmesgs(self):
        flags = 0

        try:
            while True:
                bytedata = self._udpsock.recv(MAX_UDP_BUFSIZE, flags)
                src, tstamp, data = pickle.loads(bytedata)
                if not isinstance(src, EndPoint):
                    raise TypeError()
                else:
                    yield (src, tstamp, data)
        except socket.error as e:
            self._log.debug("socket.error occured, terminating receive loop.")


# Auxiliary datastructures:
class Node(object):
    __slots__ = ['prev', 'next', 'me']
    def __init__(self, prev, me):
        self.prev = prev
        self.me = me
        self.next = None
    def __str__(self):
        return str(self.me)
    def __repr__(self):
        return self.me.__repr__()

class LRU:
    """
    Implementation of a length-limited O(1) LRU queue.
    Built for and used by PyPE:
    http://pype.sourceforge.net
    Copyright 2003 Josiah Carlson.
    """
    def __init__(self, count, pairs=[]):
        self.count = max(count, 1)
        self.d = {}
        self.first = None
        self.last = None
        for key, value in pairs:
            self[key] = value
    def __contains__(self, obj):
        return obj in self.d
    def __getitem__(self, obj):
        a = self.d[obj].me
        self[a[0]] = a[1]
        return a[1]
    def __setitem__(self, obj, val):
        if obj in self.d:
            del self[obj]
        nobj = Node(self.last, (obj, val))
        if self.first is None:
            self.first = nobj
        if self.last:
            self.last.next = nobj
        self.last = nobj
        self.d[obj] = nobj
        if len(self.d) > self.count:
            if self.first == self.last:
                self.first = None
                self.last = None
                return
            a = self.first
            a.next.prev = None
            self.first = a.next
            a.next = None
            del self.d[a.me[0]]
            del a
    def __delitem__(self, obj):
        nobj = self.d[obj]
        if nobj.prev:
            nobj.prev.next = nobj.next
        else:
            self.first = nobj.next
        if nobj.next:
            nobj.next.prev = nobj.prev
        else:
            self.last = nobj.prev
        del self.d[obj]
    def __iter__(self):
        cur = self.first
        while cur != None:
            cur2 = cur.next
            yield cur.me[1]
            cur = cur2
    def __str__(self):
        return str(self.d)
    def __repr__(self):
        return self.d.__repr__()
    def iteritems(self):
        cur = self.first
        while cur != None:
            cur2 = cur.next
            yield cur.me
            cur = cur2
    def iterkeys(self):
        return iter(self.d)
    def itervalues(self):
        for i,j in self.iteritems():
            yield j
    def keys(self):
        return self.d.keys()
    def get(self, k, d=None):
        v = self.d.get(k)
        if v is None: return None
        a = v.me
        self[a[0]] = a[1]
        return a[1]
