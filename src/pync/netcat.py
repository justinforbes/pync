# -*- coding: utf-8 -*-

"""
pync - arbitrary TCP and UDP connections and listens (Netcat for Python).
"""

from __future__ import unicode_literals
import argparse
import contextlib
import errno
import itertools
import logging
import random
import select
import shlex
import socket
import subprocess
import sys
import time

import socks

from .argparsing import GroupingArgumentParser
from . import compat
from .conin import NonBlockingConsoleInput as ConsoleInput


TOSKEYWORDS = dict(
        af11=0x28,
        af12=0x30,
        af21=0x38,
        af22=0x50,
        af23=0x58,
        af31=0x68,
        af32=0x70,
        af33=0x78,
        af41=0x88,
        af42=0x90,
        af43=0x98,
        critical=0xa0,
        cs0=0x00,
        cs1=0x20,
        cs2=0x40,
        cs3=0x60,
        cs4=0x80,
        cs5=0xa0,
        cs6=0xc0,
        cs7=0xe0,
        ef=0xb8,
        inetcontrol=0xc0,
        lowcost=0x02,
        lowdelay=0x10,
        netcontrol=0xe0,
        reliability=0x04,
        throughput=0x08,
)


class NetcatError(Exception):
    
    def __init__(self, msg, *args):
        super(NetcatError, self).__init__(msg, *args)
        self.msg = msg 

    def __str__(self):
        return self.msg


class NetcatSocketError(NetcatError):
    
    def __init__(self, socket_err, *args):
        msg = str(socket_err)
        super(NetcatSocketError, self).__init__(msg, socket_err, *args)
        self.socket_err = socket_err


class NetcatProxyError(NetcatError):
    
    def __init__(self, proxy_err, *args):
        msg = str(proxy_err)
        if proxy_err.socket_err is not None:
            msg = str(proxy_err.socket_err)
        super(NetcatProxyError, self).__init__(msg, proxy_err, *args)
        self.proxy_err =  proxy_err


class NetcatContext(object):
    D = False
    v = False
    stdin = sys.stdin
    stdout = sys.stdout
    stderr = sys.stderr

    def __init__(self,
            D=None,
            v=None,
            stdin=None, stdout=None, stderr=None, **kwargs):

        if D is not None:
            self.D = D
        if v is not None:
            self.v = v

        self.stdin = stdin or self.stdin
        self.stdout = stdout or self.stdout
        self.stderr = stderr or self.stderr

        self._init_kwargs(**kwargs)

    def _init_kwargs(self, **kwargs):
        """
        Override this to parse and initialize
        any unknown keyword arguments
        """
        if kwargs:
            raise ValueError(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        """
        Override to add any cleanup code.
        """
        pass

    def _print_message(self, message, file=None):
        if message:
            if file is None:
                file = self.stderr
            try:
                file.write(message+'\n')
            except TypeError:
                file.write(message.encode()+b'\n')
            file.flush()

    def print_verbose(self, message):
        if self.v:
            self._print_message(message, file=self.stderr)

    def print_debug(self, message):
        if self.D:
            self._print_message(message, file=self.stderr)


class NetcatConnection(NetcatContext):
    """
    Wraps a socket object to provide Netcat-like functionality.

    :param q: Quit the readwrite loop after EOF on stdin and delay of secs.
    :type q: int, optional

    You can use sub-classes of this class as a context manager using the "with" statement:

    .. code-block:: python

       with NetcatConnection(...) as nc:
           nc.readwrite()

    If you choose not to use the "with" statement, please make sure to use
    the close() method after use:

    .. code-block:: python

       nc = NetcatConnection(...)
       nc.readwrite()
       nc.close()
    """

    C = False
    d = False
    i = 0
    q = 0
    w = None
    plen = 2048

    def __init__(self, net, C=None, d=None, i=None, q=None, w=None, **kwargs):
        super(NetcatConnection, self).__init__(**kwargs)

        self.net = net

        if C is not None:
            self.C = C
        if d is not None:
            self.d = d
        if i is not None:
            self.i = i
        if q is not None:
            self.q = q
        if w is not None:
            self.w = w

        self.dest, self.port = self._getpeername(net)

        # TODO: Move this into a property.setter?
        if self.stdin is sys.__stdin__ and self.stdin.isatty():
            self.stdin = ConsoleInput()

    @classmethod
    def connect(cls, dest, port, **kwargs):
        """
        Factory method to connect to a server and return a NetcatConnection
        instance.
        This method should be implemented by a sub-class.

        :param dest: The destination hostname or IP address to connect to.
        :type dest: str

        :param port: The port number to connect to.
        :type port: int

        :param kwargs: Any other keyword arguments get passed to __init__.

        :returns: Returns a subclass of :class:`pync.NetcatConnection` once
            a connection has been established.
        :rtype: :class:`pync.NetcatConnection`

        :Example:

        .. code-block:: python

           with NetcatConnection.connect('localhost', 8000) as conn:
               conn.readwrite()
        """
        raise NotImplementedError

    @classmethod
    def listen(cls, dest, port, **kwargs):
        """
        Factory method to listen for a connection and return a NetcatConnection
        instance.
        This method should be implemented by a sub-class.

        :param dest: The hostname or IP address to bind to.
        :type dest: str

        :param port: The port number to bind to.
        :type port: int

        :param kwargs: Any other keyword arguments get passed to __init__.

        :returns: Returns a subclass of :class:`pync.NetcatConnection` once a
            connection has been established.
        :rtype: :class:`pync.NetcatConnection`

        :Example:

        .. code-block:: python

           with NetcatConnection.listen('localhost', 8000) as conn:
               conn.readwrite()
        """
        raise NotImplementedError

    @property
    def timeout(self):
        return self.w

    def _getpeername(self, sock):
        try:
            # IPv4
            dest, port = sock.getpeername()
        except ValueError:
            # IPv6
            dest, port, _, _ = sock.getpeername()
        return dest, port

    def recv(self, n, blocking=True):
        if blocking:
            return self.net.recv(n)
        try:
            can_read, _, _ = select.select([self.net], [], [], .001)
        except ValueError:
            return self.net.recv(n)

        if self.net in can_read:
            return self.net.recv(n)

    def send(self, data):
        self.net.sendall(data)

    def close(self):
        self.net.close()

    def shutdown(self, how):
        try:
            return self.net.shutdown(how)
        except (socket.error, OSError):
            pass

    def shutdown_rd(self):
        self.shutdown(socket.SHUT_RD)

    def shutdown_wr(self):
        self.shutdown(socket.SHUT_WR)

    def readwrite(self):
        """
        The main loop to read and write i_o.
        Read from stdin and send to network.
        Receive from network and write to stdout.
        Write verbose/debug/error messages to stderr.

        This loop is based on the netcat-openbsd 1.105-7 ubuntu version.

        :Example:

        .. code-block:: python

           with NetcatConnection(sock) as nc:
               nc.readwrite()
        """
        netin_eof = False
        stdin_eof = None

        idle_time = time.time()

        # (     )
        #   O O
        while(1<2):
            try:
                if netin_eof:
                    break

                if self.i:
                    time.sleep(self.i)

                # netin
                try:
                    net_data = self.recv(self.plen, blocking=False)
                except (socket.error, OSError):
                    return
                if net_data:
                    # stdout
                    try:
                        # py3 write bytes
                        self.stdout.buffer.write(net_data)
                    except AttributeError:
                        # py2 write bytes
                        self.stdout.write(net_data)
                    self.stdout.flush()
                    idle_time = time.time()
                elif net_data is not None:
                    # netin EOF
                    self.shutdown_rd()
                    netin_eof = True

                # stdin
                if not self.d:
                    try:
                        # py3 read bytes
                        stdin_data = self.stdin.buffer.read(self.plen)
                    except AttributeError:
                        # py2 read bytes
                        stdin_data = self.stdin.read(self.plen)

                    # netout
                    if stdin_data:
                        if self.C:
                            stdin_data = stdin_data.replace(b'\n', b'\r\n')
                        try:
                            self.send(stdin_data)
                        except socket.error as e:
                            if e.errno != errno.EPIPE:
                                # Not a broken pipe.
                                raise
                            # Broken pipe.
                            # netin connection lost
                            return
                        idle_time = time.time()
                    elif stdin_data is not None:
                        # stdin EOF
                        if not stdin_eof:
                            stdin_eof = time.time()
                        # If the user asked to exit on EOF, do it
                        if self.q == 0:
                            self.shutdown_wr()
                            #self.stdin.close()
                        # If the user asked to die after a while, arrange for it
                        if self.q > 0:
                            stdin_eof_elapsed = time.time() - stdin_eof
                            if stdin_eof_elapsed >= self.q:
                                return
                    
                    if self.timeout is not None:
                        idle_time_elapsed = time.time() - idle_time
                        if idle_time_elapsed >= self.timeout:
                            return
            except StopReadWrite:
                # I/O has requested to stop the readwrite loop.
                break


class NetcatTCPConnection(NetcatConnection):
    """
    Wraps a TCP socket to provide Netcat-like functionality.
    """

    @classmethod
    def connect(cls, dest, port, **kwargs):
        """
        Factory method to connect to a TCP server and return a
        :class:`pync.NetcatTCPConnection` object.

        :param dest: The destination hostname or IP address to connect to.
        :type dest: str

        :param port: The port number to connect to.
        :type port: int

        :param kwargs: Any other keyword arguments get passed to __init__.

        :rtype: :class:`pync.NetcatTCPConnection`

        :Example:

        .. code-block:: python
           
           from pync import NetcatTCPConnection
           with NetcatTCPConnection.connect('localhost', 8000) as conn:
               conn.readwrite()
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((dest, port))
        return cls(sock, **kwargs)

    @classmethod
    def listen(cls, dest, port, **kwargs):
        """
        Factory method to listen for an incoming TCP connection and
        return a :class:`pync.NetcatTCPConnection` object.

        :param dest: The destination hostname or IP address to bind to.
        :type dest: str

        :param port: The port number to bind to.
        :type port: int

        :param kwargs: Any other keyword arguments get passed to __init__.

        :rtype: :class:`pync.NetcatTCPConnection`

        :Example:

        .. code-block:: python

           from pync import NetcatTCPConnection
           with NetcatTCPConnection.listen('localhost', 8000) as conn:
               conn.readwrite()
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((dest, port))
        server_sock.listen(1)

        # ctrl-c interrupt doesn't seem to break out of server accept.
        # So using select for non-blocking server accept.
        while True:
            readables, _, _ = select.select([server_sock], [], [], .002)
            if server_sock in readables:
                sock, _ = server_sock.accept()
                break

        server_sock.close()
        return cls(sock, **kwargs)


class NetcatUDPConnection(NetcatConnection):
    """
    Wraps a UDP socket object to provide Netcat-like functionality.
    """
    
    @classmethod
    def connect(cls, dest, port, **kwargs):
        """
        :TODO:
        """
        # TODO
        raise NotImplementedError

    @classmethod
    def listen(cls, dest, port, **kwargs):
        """
        :TODO:
        """
        raise NotImplementedError

    def recv(self, *args, **kwargs):
        try:
            return super(NetcatUDPConnection, self).recv(*args, **kwargs)
        except (socket.error, compat.ConnectionRefusedError):
            raise StopReadWrite


class ConnectionRefused(Exception):
    '''
    Same as ConnectionRefusedError but passes back the
    dest and port of the refused connection.
    '''

    def __init__(self, dest, port):
        self.dest = dest
        self.port = port


class NetcatIterator(NetcatContext):
    '''
    Base class for Netcat clients and servers.

    NetcatClients can iterate through one or more ports
    and NetcatServers can accept one or more connections.
    '''
    Connection = None
    T = None

    allow_reuse_port = True

    def __init__(self, T=None, *args, **kwargs):
        super(NetcatIterator, self).__init__(*args, **kwargs)
        if T is not None:
            self.T = T

    def _init_kwargs(self, **kwargs):
        self._conn_kwargs = kwargs

    def _init_connection(self, sock):
        inout = dict(stdin=self.stdin, stdout=self.stdout, stderr=self.stderr)
        self._conn_kwargs.update(inout)
        return self.Connection(sock, **self._conn_kwargs)

    def __iter__(self):
        return self.iter_connections()

    def __next__(self):
        return self.next_connection()

    @property
    def tos(self):
        ''' Returns IP TOS integer value. '''
        T = self.T
        if T in TOSKEYWORDS:
            T = TOSKEYWORDS[T]
        return int(T)

    def iter_connections(self):
        ''' Override in subclass
        Iterate through and yield each connection.
        Close each connection before moving on to the next.
        '''
        raise NotImplementedError

    def next_connection(self):
        ''' Override in subclass
        Return the next NetcatConnection.
        '''
        raise NotImplementedError

    def readwrite(self):
        for conn in self:
            conn.readwrite()

    def _set_common_sockopts(self, sock):
        if self.allow_reuse_port:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.b:
            sock.setsockopt(socket.IPPROTO_TCP, socket.SO_BROADCAST, 1)
        if self.D:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_DEBUG, 1)
        if self.T:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, self.tos)
        if self.I:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.I)
        if self.O:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.O)

    def _getaddrinfo(self, addr, port):
        # Used to raise socket error on bad address.
        try:
            return socket.getaddrinfo(
                    addr, port,
                    self.address_family, 0, 0, self.flags,
            )
        except socket.error as e:
            raise NetcatSocketError(e)


class NetcatClient(NetcatIterator):
    """
    A Netcat client is iterable.
    You can pass one or more ports and iterate through
    each :class:`pync.NetcatConnection`.

    :param dest: The destination hostname or IP address to connect to.
    :type dest: str

    :param port: The port number(s) to connect to.
    :type port: int, list(int)

    :param e: Execute a command upon connection.
    :type e: str, optional

    :param z: Set to True to turn Zero i_o on (connect then close).
        Useful for simple port scanning.
    :type z: bool, optional

    You can use sub-classes of this class as a context manager using the "with" statement:

    .. code-block:: python

       with NetcatClient(...) as nc:
           nc.readwrite()

    If you choose not to use the "with" statement, please make sure to use
    the close() method after use:

    .. code-block:: python

       nc = NetcatClient(...)
       nc.readwrite()
       nc.close()

    :Example:

    .. code-block:: python
       :caption: We can connect to multiple ports one after another by passing
           a list of ports.

       with NetcatClient('localhost', [8000, 8001]) as nc:
           for connection in nc:
               connection.readwrite()

    .. code-block:: python
       :caption: Using the "z" and "v" options, we can perform a simple port scan.

       with NetcatClient('localhost', [8000, 8002], z=True, v=True) as nc:
           nc.readwrite()
    """
    protocol_name = ''

    address_family = socket.AF_INET
    socket_type = None

    v_conn_succeeded = 'Connection to {dest} {port} port [{proto_name}/{proto}] succeeded!'
    v_conn_refused = 'connect to {dest} port {port} ({proto_name}) failed: Connection refused'

    _4 = True
    _6 = False
    b = False
    D = False
    I = None
    n = False
    O = None
    P = None
    p = 0
    r = False
    s = ''
    w = None
    X = '5'
    x = None
    z = False

    def __init__(self, dest, port,
            _4=None, _6=None, b=None, D=None, I=None,
            n=None, O=None, P=None, p=None, r=None, s=None, w=None,
            X=None, x=None, z=None, **kwargs):
        super(NetcatClient, self).__init__(**kwargs)

        self.dest, self.port = dest, port
        if _4 is not None:
            self._4 = _4
        if _6 is not None:
            self._6 = _6
        if b is not None:
            self.b = b
        if D is not None:
            self.D = D
        if I is not None:
            self.I = I
        if n is not None:
            self.n = n
        if O is not None:
            self.O = O
        if p is not None:
            self.p = p
        if r is not None:
            self.r = r
        if s is not None:
            self.s = s
        if w is not None:
            self.w = w
        if X is not None:
            self.X = X
        if x is not None:
            self.x = x
        if z is not None:
            self.z = z

        self._conn_kwargs['w'] = self.w
        
        if isinstance(self.port, int):
            # Only one port passed, wrap it in a list
            # for the __iter__ function.
            self.port = [self.port]

        if self.r:
            self.port = list(self.port)
            random.shuffle(self.port)
        self._iterports = iter(self.port)

        if self._6:
            self.address_family = socket.AF_INET6
        self.flags = 0
        if self.n:
            self.flags = socket.AI_NUMERICHOST

    @property
    def proxy_protocol(self):
        protocols = {
                '5': socks.SOCKS5,
                '4': socks.SOCKS4,
                'connect': socks.HTTP
        }
        return protocols[self.X]

    @property
    def proxy_address(self):
        return self.x.split(':', 1)[0]

    @property
    def proxy_port(self):
        defaults = {
                '5': 1080,
                '4': 1080,
                'connect': 3128,
        }

        try:
            port = self.x.split(':', 1)[1]
        except IndexError:
            port = defaults[self.X]

        try:
            port = int(port)
        except (TypeError, ValueError):
            port = repr(port)
        return port

    @property
    def timeout(self):
        return self.w

    def iter_connections(self):
        while True:
            try:
                nc_conn = self.next_connection()
            except StopIteration:
                # No more ports to connect to.
                # Exit loop
                return
            except ConnectionRefused:
                # Move onto next connection if any errors.
                continue

            try:
                if not self.z:
                    yield nc_conn
            finally:
                nc_conn.close()

    def _conn_refused(self, port, dest=None):
        if dest is None:
            dest = self.dest
        self.print_verbose(
                self.v_conn_refused.format(
                    dest=dest, port=port,
                    proto_name=self.protocol_name,
                ),
        )
        raise ConnectionRefused(self.dest, port)

    def next_connection(self):
        # This will raise StopIteration when no more ports.
        port = next(self._iterports)
        try:
            nc_conn = self._create_connection((self.dest, port))
        except compat.ConnectionRefusedError:
            self._conn_refused(port)
        except socks.ProxyError as e:
            if e.socket_err and e.socket_err.errno == errno.ECONNREFUSED:
                self._conn_refused(self.proxy_port,
                        dest=self.proxy_address,
                )
            raise NetcatProxyError(e)
        except socket.error as e:
            if e.errno != errno.ECONNREFUSED:
                raise NetcatSocketError(e)
            self._conn_refused(port)
        else:
            self._conn_succeeded(port)

        if self.z:
            # If zero io mode, close the connection.
            nc_conn.close()

        return nc_conn

    def _conn_succeeded(self, port, dest=None):
        if dest is None:
            dest = self.dest
        proto = '*'
        if not self.n:
            try:
                proto = socket.getservbyport(port, self.protocol_name)
            except (socket.error, OSError):
                pass
        self.print_verbose(
                self.v_conn_succeeded.format(
                    dest=dest,
                    port=port,
                    proto_name=self.protocol_name,
                    proto=proto,
                ),
        )
    
    def _create_connection(self, addr):
        dest, port = addr
        addrinfo = self._getaddrinfo(dest, port)
        sock = self._client_init()
        self._client_bind(sock)
        self._client_connect(sock, addr)
        nc_conn = self._init_connection(sock)
        return nc_conn

    def _client_init(self):
        if self.x:
            # proxy socket
            addrinfo = self._getaddrinfo(self.proxy_address, self.proxy_port)
            s = socks.socksocket(self.address_family, self.socket_type)
            s.set_proxy(
                    proxy_type=self.proxy_protocol,
                    addr=self.proxy_address,
                    port=self.proxy_port,
                    username=self.P,
            )
            return s
        return socket.socket(self.address_family, self.socket_type)

    def _client_bind(self, sock):
        self._set_common_sockopts(sock)
        if self.s or self.p:
            source = self.s or None
            port = self.p or None
            addrinfo = self._getaddrinfo(source, port)
        sock.bind((self.s, self.p))

    def _client_connect(self, sock, addr):
        if self.timeout:
            sock.settimeout(self.timeout)
        sock.connect(addr)
        sock.settimeout(None)


class NetcatTCPClient(NetcatClient):
    """
    A :class:`pync.NetcatClient` for the Transmission Control Protocol.
    """
    protocol_name = 'tcp'
    Connection = NetcatTCPConnection

    socket_type = socket.SOCK_STREAM


class NetcatUDPClient(NetcatClient):
    """
    A :class:`pync.NetcatClient` for the User Datagram Protocol.
    """
    protocol_name = 'udp'
    Connection = NetcatUDPConnection

    socket_type = socket.SOCK_DGRAM

    udp_scan_timeout = 3

    def _client_connect(self, sock, addr):
        super(NetcatUDPClient, self)._client_connect(sock, addr)
        self._udptest(sock)

    def _udptest(self, sock):
        for i in compat.range(2):
            sock.sendall(b'X')

        timeout = self.timeout
        if timeout is None:
            timeout = self.udp_scan_timeout

        # Give the remote host some time to reply.
        for i in compat.range(0, timeout):
            time.sleep(1)
            sock.sendall(b'X')


class NetcatServer(NetcatIterator):
    """
    A Netcat server is iterable.
    You can iterate through each incoming connection.

    :param port: The port number to bind the server to.
    :type port: int

    :param dest: The hostname or IP address to bind the server to.
    :type dest: str, optional

    :param e: Execute a command upon connection.
    :type e: str, optional

    :param k: Set to True to keep the server open between connections.
    :type k: bool, optional

    :param kwargs: Any other keyword arguments get passed to each
        connection.

    You can use sub-classes of this class as a context manager using the "with" statement:

    .. code-block:: python

       with NetcatServer(...) as nc:
           nc.readwrite()

    If you don't use the "with" statement, please make sure to use the
    close() method after use:

    .. code-block:: python
       
       nc = NetcatServer(...)
       nc.readwrite()
       nc.close()

    :Example:

    .. code-block:: python
       :caption: Use the "k" option to keep the server open and iterate
           through each :class:`pync.NetcatConnection`.

       with NetcatServer(8000, dest='localhost', k=True) as nc:
           for connection in nc:
               connection.readwrite()
    """
    protocol_name = ''

    address_family = socket.AF_INET
    socket_type = None

    v_listening = 'Listening on [{dest}] (family {family}, port {port})'
    v_conn_accepted = 'Connection from [{dest}] port {port} [{proto_name}/{proto}] accepted (family {family}, sport {sport})'
    v_listening_again = 'Connection closed, listening again.'

    _4 = True
    _6 = False
    b = False
    D = False
    I = None
    k = False
    n = False
    O = None

    def __init__(self, port, dest='', _4=None, _6=None, b=None,
            D=None, I=None, k=None, n=None, O=None, **kwargs):
        super(NetcatServer, self).__init__(**kwargs)

        self.dest = dest
        if dest == '':
            # getaddrinfo doesn't accept an empty string.
            # set to 0.0.0.0 to listen on all interfaces.
            self.dest = '0.0.0.0'

        self.port = port
        if not isinstance(port, int) and not isinstance(port, str):
            # port is not an int or a string.
            # getaddrinfo expects an int or string.
            # All objects have __repr__ so call repr to get string.
            self.port = repr(port)

        if _4 is not None:
            self._4 = _4
        if _6 is not None:
            self._6 = _6
        if b is not None:
            self.b = b
        if D is not None:
            self.D = D
        if I is not None:
            self.I = I
        if k is not None:
            self.k = k
        if n is not None:
            self.n = n
        if O is not None:
            self.O = O

        if _6:
            self.address_family = socket.AF_INET6
        self.flags = 0
        if self.n:
            self.flags = socket.AI_NUMERICHOST

        self._sock = socket.socket(self.address_family, self.socket_type)

        bind_and_activate = True
        if bind_and_activate:
            try:
                self._server_bind()
                self._server_activate()
            except:
                self._server_close()
                raise

    def _listening(self):
        self.print_verbose(self.v_listening.format(
            dest=self.dest,
            family=self.address_family,
            port=self.port,
        ))

    def _listening_again(self):
        self.print_verbose(self.v_listening_again)

    def iter_connections(self):
        self._listening()
        try:
            nc_conn = self.next_connection()
        except StopIteration:
            return

        try:
            yield nc_conn
        finally:
            self._close_request(nc_conn)

        if self.k:
            while True:
                self._listening_again()
                try:
                    nc_conn = self.next_connection()
                except StopIteration:
                    return

                try:
                    yield nc_conn
                finally:
                    self._close_request(nc_conn)

    def _conn_accepted(self, cli_dest, cli_port):
        proto = '*'
        if not self.n:
            try:
                proto = socket.getservbyport(self.port, self.protocol_name)
            except (socket.error, OSError):
                pass
        self.print_verbose(self.v_conn_accepted.format(
            dest=cli_dest,
            port=self.port,
            proto_name=self.protocol_name,
            proto=proto,
            family=self.address_family,
            sport=cli_port,
        ))

    def next_connection(self):
        while True:
            try:
                can_read, _, _ = select.select([self._sock], [], [], .002)
            except (ValueError, socket.error):
                # Bad / closed socket.
                # This can occur when the server is closed.
                raise StopIteration
            if self._sock in can_read:
                cli_sock, cli_addr = self._get_request()
                try:
                    # IPv4
                    cli_dest, cli_port = cli_addr
                except ValueError:
                    # IPv6
                    cli_dest, cli_port, _, _ = cli_addr
                nc_conn = self._init_connection(cli_sock)
                break
        self._conn_accepted(cli_dest, cli_port)
        return nc_conn

    def _server_bind(self):
        addrinfo = self._getaddrinfo(self.dest, self.port)
        self._set_common_sockopts(self._sock)
        try:
            self._sock.bind((self.dest, self.port))
        except socket.error as e:
            raise NetcatSocketError(e)

    def _server_activate(self):
        pass

    def _server_close(self):
        self._sock.close()

    def _get_request(self):
        ''' Override in subclass
        Accept connection.
        Return (socket, addr) tuple.
        '''
        raise NotImplementedError

    def _close_request(self, request):
        request.close()

    def close(self):
        """
        Close the server.
        """
        self._server_close()


class NetcatTCPServer(NetcatServer):
    """
    A :class:`pync.NetcatServer` for the Transmission Control Protocol.
    """
    protocol_name = 'tcp'
    Connection = NetcatTCPConnection

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1

    def next_connection(self):
        nc_conn = super(NetcatTCPServer, self).next_connection()
        if not self.k:
            self.close()
        return nc_conn

    def _server_activate(self):
        self._sock.listen(self.request_queue_size)

    def _get_request(self):
        return self._sock.accept()


class NetcatUDPServer(NetcatServer):
    """
    A :class:`pync.NetcatServer` for the User Datagram Protocol.
    """
    protocol_name = 'udp'
    Connection = NetcatUDPConnection

    address_family = socket.AF_INET
    socket_type = socket.SOCK_DGRAM
    max_packet_size = 8192

    def _get_request(self):
        data, addr = self._sock.recvfrom(self.max_packet_size)
        try:
            # py3
            self.stdout.buffer.write(data)
        except AttributeError:
            # py2
            self.stdout.write(data)

        self._sock.connect(addr)
        return self._sock, addr

    def _close_request(self, request):
        if not self.k:
            request.close()


class StopReadWrite(Exception):
    """
    Exception to stop the readwrite loop.
    """


class NetcatPortAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        # If one port is given on the command line, set that as value.
        # If more that one is given, sort and chain as one iterator.

        if not values:
            return

        if len(values) == 1 and values[0].start == (values[0].stop - 1):
            # Only one port given.
            setattr(namespace, self.dest, values[0].start)
            return

        # sort the list of port ranges.
        sorted_values = sorted(values, key=lambda r: r.start)
        # chain the port ranges into one iter.
        chained_values = itertools.chain(*sorted_values)
        setattr(namespace, self.dest, chained_values)
        return


class NetcatArgumentParser(GroupingArgumentParser):
    prog = 'Netcat'
    usage = ("%(prog)s [-46bCDdhklnruvz] [-I length] [-i interval] [-O length]"
            "\n\t    [-P proxy_username] [-p source_port] [-q seconds]"
            "\n\t    [-s source] [-T toskeyword] [-w timeout] [-X proxy_protocol]"
            "\n\t    [-x proxy_address[:port]] [dest] [port]")
    description = 'arbitrary TCP and UDP connections and listens (Netcat for Python).'
    add_help = False
    
    PortAction = NetcatPortAction

    def __init__(self, *args, **kwargs):
        super(NetcatArgumentParser, self).__init__(*args, **kwargs)

        self.add_argument('-4',
                help='Use IPv4',
                action='store_true',
                dest='_4',
        )

        self.add_argument('-6',
                help='Use IPv6',
                action='store_true',
                dest='_6',
        )

        self.add_argument('-b',
                help='Allow broadcast',
                action='store_true',
        )

        self.add_argument('-C',
                help='Send CRLF as line-ending',
                action='store_true',
        )

        self.add_argument('-D',
                help='Enable the debug socket option',
                action='store_true',
        )

        self.add_argument('-d',
                help='Detach from stdin',
                action='store_true',
        )

        self.add_argument('-h',
                help='show this help message and exit.',
                action='help',
        )

        self.add_argument('-I',
                help='TCP receive buffer length',
                metavar='length',
                type=int,
        )

        self.add_argument('-i',
                help='Delay interval for lines sent, ports scanned',
                type=int,
                metavar='secs',
        )

        self.add_argument('-k',
                group='server arguments',
                help='Keep inbound sockets open for multiple connects',
                action='store_true',
        )

        self.add_argument('-l',
                group='server arguments',
                help='Listen mode, for inbound connects',
                action='store_true',
        )

        self.add_argument('-n',
                help='Suppress name/port resolutions',
                action='store_true',
        )

        self.add_argument('-O',
                help='TCP send buffer length',
                metavar='length',
                type=int,
        )

        self.add_argument('-P',
                group='client arguments',
                help='Username for proxy authentication',
                metavar='proxy_username',
        )

        self.add_argument('-p',
                help='Specify local port for remote connects',
                metavar='source_port',
                type=self.source_port,
        )

        self.add_argument('-q',
                help='quit after EOF on stdin and delay of seconds',
                metavar='seconds',
                default=0,
                type=int,
        )

        self.add_argument('-r',
                group='client arguments',
                help='Randomize remote ports',
                action='store_true',
        )

        self.add_argument('-s',
                group='client arguments',
                help='Local source address',
                metavar='source',
        )

        self.add_argument('-T',
                help='Set IP Type of Service',
                metavar='toskeyword',
                type=self.toskeyword,
        )

        self.add_argument('-u',
                help='UDP mode [default: TCP]',
                action='store_true',
        )

        self.add_argument('-v',
                help='Verbose',
                action='store_true',
        )

        self.add_argument('-w',
                help='Timeout for connects and final net reads',
                metavar='secs',
                type=self.timeout,
        )

        self.add_argument('-X',
                group='client arguments',
                help='Proxy protocol: "4", "5" (SOCKS) or "connect"',
                metavar='proxy_protocol',
                choices=['5', '4', 'connect'],
                default='5',
        )

        self.add_argument('-x',
                group='client arguments',
                help='Specify proxy address and port',
                metavar='proxy_address[:port]',
        )

        self.add_argument('-z',
                group='client arguments',
                help='Zero-I/O mode [used for scanning]',
                action='store_true',
        )

        self.add_argument('dest',
                help='The destination host name or ip to connect or bind to',
                nargs='?',
                default='',
                metavar='dest',
        )

        self.add_argument('port',
                help='The port number to connect or bind to',
                type=self.port,
                metavar='port',
                nargs='*',
                action=self.PortAction,
        )

    def _valid_port(self, value):
        return 1 <= int(value) <= 65535

    def timeout(self, value):
        value = int(value)
        if value < 0:
            raise ValueError('timeout too small')
        return value

    def toskeyword(self, value):
        if value in TOSKEYWORDS:
            return TOSKEYWORDS[value]
        try:
            value = int(value)
        except ValueError:
            # value might be a hex number.
            value = int(value, 16)
        if 0 <= value <= 255:
            return value
        raise ValueError('illegal tos value {}'.format(value))

    def source_port(self, value):
        msg = 'invalid source_port value: {}'
        if not self._valid_port(value):
            raise ValueError(msg.format(value))
        return int(value)

    def port(self, value):
        # This should always return a range of ports.
        # Even if only one port is given.
        #
        # The PortAction then turns it into a single port
        # if one port is given or a chain of sorted port
        # ranges if more than one port is given.

        msg = 'invalid port value: {}'
        try:
            # assume port value is a range.
            # e.g 8000-8005
            start_port, end_port = [int(x) for x in value.split('-')]
        except ValueError:
            # port value is not a range.
            value = int(value)
            if not self._valid_port(value):
                raise ValueError(msg.format(value))
            return compat.range(value, value+1)

        if start_port > end_port:
            start_port, end_port = end_port, start_port

        for p in [start_port, end_port]:
            if not self._valid_port(p):
                raise ValueError(msg.format(p))

        return compat.range(start_port, end_port+1)

    def parse_args(self, args):
        grouped_args = self.group_parse_args(args)

        args = grouped_args['general arguments']
        client_args = grouped_args['client arguments']
        server_args = grouped_args['server arguments']

        if server_args.l:
            # Server mode.
            if args.dest and args.port and not args.p:
                # pync -l localhost 8000
                pass
            elif args.dest and not args.port and not args.p:
                # pync -l 8000
                # Get the port from args.dest.
                # This will need feeding through the parser
                # again to detect any port number errors.
                args.port = args.dest
                args.dest = ''
                test_args = ['dest', args.port]
                test_args = self.group_parse_args(test_args)['general arguments']
                args.port = test_args.port
            elif not args.dest and not args.port and args.p:
                # pync -lp 8000
                pass
            elif args.dest and not args.port and args.p:
                # pync -lp 8000 localhost
                pass
            elif args.dest and args.port and args.p:
                # pync -lp 8000 localhost 8001
                pass
            else:
                self.print_usage()
                self.exit()
        else:
            # Client mode.
            if args.dest and args.port:
                # pync localhost 8000
                pass
            elif args.dest and args.port and args.p:
                # pync -p 1234 localhost 8000
                pass
            else:
                self.print_usage()
                self.exit()

        kwargs = dict()
        kwargs.update(vars(args))
        if server_args.l:
            kwargs.update(vars(server_args))
        else:
            kwargs.update(vars(client_args))

        return argparse.Namespace(**kwargs)


class Netcat(object):
    """
    Factory class that returns the correct Netcat object based
    on the arguments given.

    :param dest: The IP address or hostname to connect or bind to depending
        on the "l" parameter.
    :type dest: str, optional

    :param port: The port number to connect or bind to depending on the "l" parameter.
    :type port: int, list(int)

    :param l: Set to True to create a server and listen for incoming connections.
    :type l: bool, optional

    :param u: Set to True to use UDP for transport instead of the default TCP.
    :type u: bool, optional

    :param p: The source port number to bind to.
    :type p: int, optional

    :param kwargs: All other keyword arguments get passed to the underlying
        Netcat class.

    You can use this class as a context manager using the "with" statement:

    .. code-block:: python

       with Netcat(...) as nc:
           nc.readwrite()

    If you use it without the "with" statement, please make sure to use the
    close method after use:

    .. code-block:: python

       nc = Netcat(...)
       nc.readwrite()
       nc.close()

    :Examples:

    .. code-block:: python
       :caption: Use the "l" option to create a :class:`pync.NetcatTCPServer`
           object.

       from pync import Netcat
       with Netcat(dest='localhost', port=8000, l=True) as nc:
           nc.readwrite()

    .. code-block:: python
       :caption: By default, without the "l" option, Netcat will return a
           :class:`pync.NetcatTCPClient` object.

       from pync import Netcat
       with Netcat(dest='localhost', port=8000) as nc:
           nc.readwrite()

    .. code-block:: python
       :caption: Create a :class:`pync.NetcatUDPServer` with the "u" and "l" options.

       from pync import Netcat
       with Netcat(dest='localhost', port=8000, l=True, u=True) as nc:
           nc.readwrite()

    .. code-block:: python
       :caption: And a :class:`pync.NetcatUDPClient` using only the "u" option.

       from pync import Netcat
       with Netcat(dest='localhost', port=8000, u=True) as nc:
           nc.readwrite()

    .. code-block:: python
       :caption: Any other keyword arguments get passed to the underlying Netcat class.

       from pync import Netcat
       # Use the "k" option to keep the server open between connections.
       with Netcat(dest='localhost', port=8000, l=True, k=True) as nc:
           nc.readwrite()

    .. code-block:: python
       :caption: Pass a list of ports to connect to one after the other.

       # Simple port scan example.
       from pync import Netcat
       # Use the "z" option to turn Zero i_o on (connect then close).
       # Use the "v" option to turn verbose output on to see connection success or failure.
       ports = [8000, 8003, 8002]
       with Netcat(dest='localhost', port=ports, z=True, v=True) as nc:
           nc.readwrite()
    """
    ArgumentParser = NetcatArgumentParser

    TCPClient = NetcatTCPClient
    TCPServer = NetcatTCPServer
    UDPClient = NetcatUDPClient
    UDPServer = NetcatUDPServer

    stdin = sys.stdin
    stdout = sys.stdout
    stderr = sys.stderr

    def __new__(cls, dest='', port=None, l=False, u=False, p=None,
            stdin=None, stdout=None, stderr=None, **kwargs):
        stdin = stdin or cls.stdin
        stdout = stdout or cls.stdout
        stderr = stderr or cls.stderr

        kwargs.update(dict(
            stdin=stdin,
            stdout=stdout,
            stderr=stderr))

        if l:
            if p is not None:
                port = p
            if u:
                return cls.UDPServer(port, dest=dest, **kwargs)
            else:
                return cls.TCPServer(port, dest=dest, **kwargs)
        else:
            if u:
                return cls.UDPClient(dest, port, p=p, **kwargs)
            else:
                return cls.TCPClient(dest, port, p=p, **kwargs)

    @classmethod
    def from_args(cls, args, stdin=None, stdout=None, stderr=None):
        """
        Create a Netcat object from command-line arguments instead of keyword
        arguments.

        :param args: A string containing the command-line arguments to create
            the Netcat instance with.
        :type args: str

        :param stdin: A file-like object to read outgoing network data from.
        :type stdin: file, optional

        :param stdout: A file-like object to write incoming network data to.
        :type stdout: file, optional

        :param stderr: A file-like object to write verbose/debug/error messages to.
        :type stderr: file, optional

        :Example:

        .. code-block:: python

           from pync import Netcat
           with Netcat.from_args('-l localhost 8000') as nc:
               nc.readwrite()
        """
        stdin = stdin or cls.stdin
        stdout = stdout or cls.stdout
        stderr = stderr or cls.stderr

        try:
            # Assume args is a string and try to split it.
            args = shlex.split(args)
        except AttributeError:
            # args is not a string, assume it's a list.
            pass

        parser = cls.ArgumentParser(stdout=stdout, stderr=stderr)
        args = parser.parse_args(args)

        kwargs = dict()
        kwargs.update(vars(args))

        kwargs.update(dict(
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        ))

        return cls(**kwargs)


def pync(args, stdin=None, stdout=None, stderr=None, Netcat=Netcat):
    """
    Create and run a Netcat instance.
    This is similar to running **pync** from the command-line.

    :param args: A string containing command-line arguments.
    :type args: str

    :param stdin: A file-like object to read outgoing network data from.
    :type stdin: file, optional

    :param stdout: A file-like object to write incoming network data to.
    :type stdout: file, optional

    :param stderr: A file-like object to write error/verbose/debug messages to.
    :type stderr: file, optional

    :return: Error status code depending on success (0) or failure (>0).
    :rtype: int

    :Examples:

    .. code-block:: python
       :caption: Create a local TCP server on port 8000.
       
       from pync import pync
       pync('-l localhost 8000')

    .. code-block:: python
       :caption: Connect to a local TCP server on port 8000.

       from pync import pync
       pync('localhost 8000')

    .. code-block:: python
       :caption: Create a local TCP server to host a file on port 8000.

       from pync import pync
       with open('file.in', 'rb') as f:
           pync('-l localhost 8000', stdin=f)

    .. code-block:: python
       :caption: Connect to a local TCP server to download a file on
           port 8000.

       from pync import pync
       with open('file.out', 'wb') as f:
           pync('localhost 8000', stdout=f)
    """
    _stdin = stdin or Netcat.stdin
    _stdout = stdout or Netcat.stdout
    _stderr = stderr or Netcat.stderr

    exit = argparse.Namespace()
    exit.status = 1


    class PyncTCPClient(Netcat.TCPClient):
        v_conn_refused = 'pync: ' + Netcat.TCPClient.v_conn_refused

        def _conn_succeeded(self, port):
            super(PyncTCPClient, self)._conn_succeeded(port)
            exit.status = 0


    class PyncTCPServer(Netcat.TCPServer):

        def _listening(self):
            super(PyncTCPServer, self)._listening()
            exit.status = 0


    class PyncUDPClient(Netcat.UDPClient):
        v_conn_refused = 'pync: ' + Netcat.UDPClient.v_conn_refused
        
        def _conn_succeeded(self, port):
            super(PyncUDPClient, self)._conn_succeeded(port)
            exit.status = 0


    class PyncUDPServer(Netcat.UDPServer):

        def _listening(self):
            super(PyncUDPServer, self)._listening()
            exit.status = 0


    class PyncArgumentParser(Netcat.ArgumentParser):
        prog = 'pync'

        def print_help(self, *args, **kwargs):
            super(PyncArgumentParser, self).print_help(*args, **kwargs)
            exit.status = 0


    class PyncNetcat(Netcat):
        ArgumentParser = PyncArgumentParser

        TCPClient = PyncTCPClient
        TCPServer = PyncTCPServer
        UDPClient = PyncUDPClient
        UDPServer = PyncUDPServer

        stdin = _stdin
        stdout = _stdout
        stderr = _stderr


    try:
        with PyncNetcat.from_args(args) as nc:
            nc.readwrite()
    except NetcatError as e:
        _stderr.write('pync: {}\n'.format(e))
        exit.status = 1
    except KeyboardInterrupt:
        _stderr.write('\n')
        exit.status = 130
    except SystemExit:
        # ArgumentParser may raise SystemExit when error or help.
        return exit.status

    return exit.status

