# -*- coding: utf-8 -*-

import pkg_resources
import sys

from .netcat import (
        pync,
        Netcat,
        NetcatArgumentParser,
        NetcatConnection,
        NetcatClient, NetcatServer,
        NetcatTCPClient, NetcatTCPServer, NetcatTCPConnection,
        NetcatUDPClient, NetcatUDPServer, NetcatUDPConnection,
        StopReadWrite, ConnectionRefused,
        ConsoleInput,
)

self = sys.modules[__name__]
for entry_point in pkg_resources.iter_entry_points('pync_plugins'):
    plugin = entry_point.load()
    plugin(self)

