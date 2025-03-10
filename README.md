<h1 align="center">
  <a href="https://github.com/brenw0rth/pync"><img src="identicon.png" alt="pync" width=50></a>
  pync
</h1>

<p align="center">
  <a href="https://github.com/brenw0rth/pync/actions/workflows/python-package.yml">
      <img src="https://github.com/brenw0rth/pync/actions/workflows/python-package.yml/badge.svg">
  </a>
  <br>
  <a href="https://readthedocs.org/projects/pync/">
    <img src="https://readthedocs.org/projects/pync/badge/?version=latest&style=flat-square">
  </a>
  <a href="https://github.com/brenw0rth/pync/blob/main/LICENSE">
      <img src="https://img.shields.io/github/license/brenw0rth/pync?style=flat-square">
  </a>
</p>

## Name
**pync** - arbitrary TCP and UDP connections and listens ([Netcat](https://en.wikipedia.org/wiki/Netcat) for Python).

## Synopsis
<details open>
<summary>Unix</summary>

```sh
pync [-46bCDdhklnruvz] [-I length] [-i interval] [-O length]
     [-P proxy_username] [-p source_port] [-q seconds]
     [-s source] [-T toskeyword] [-w timeout] [-X proxy_protocol]
     [-x proxy_address[:port]] [dest] [port]
```
</details>

<details>
<summary>Windows</summary>

```sh
py -m pync [-46bCDdhklnruvz] [-I length] [-i interval] [-O length]
           [-P proxy_username] [-p source_port] [-q seconds]
           [-s source] [-T toskeyword] [-w timeout] [-X proxy_protocol]
           [-x proxy_address[:port]] [dest] [port]
```
</details>

<details>
<summary>Python</summary>

```python
from pync import pync
args = '''[-46bCDdhklnruvz] [-I length] [-i interval] [-O length]
          [-P proxy_username] [-p source_port] [-q seconds]
          [-s source] [-T toskeyword] [-w timeout] [-X proxy_protocol]
          [-x proxy_address[:port]] [dest] [port]'''
pync(args, stdin, stdout, stderr)
```
</details>

## Description
Inspired by the [Black Hat Python](https://github.com/EONRaider/blackhat-python3) book,
the goal of **pync** was to create an easy to use library that
provides [Netcat](https://en.wikipedia.org/wiki/Netcat)-like functionality for Python developers.</br>

Common uses include:
* [Interactive client/server communication](https://pync.readthedocs.io/en/latest/examples/client-server.html)
* [Remote data transfer (upload/download)](https://pync.readthedocs.io/en/latest/examples/data-transfer.html)
* [Port scanning (simple connect scan)](https://pync.readthedocs.io/en/latest/examples/port-scanning.html)
* [Remote command execution (reverse/bind shell)](https://pync.readthedocs.io/en/latest/examples/remote-command-exec.html)

## Installation
**pync** should work on any system with  [Python](https://www.python.org/)
installed (version 2.7 or higher).

Use Python's pip command to install **pync** straight from github:
<details open>
<summary>Unix</summary>

```sh
pip install https://github.com/brenw0rth/pync/archive/main.zip
```
</details>

<details>
<summary>Windows</summary>

```sh
py -m pip install https://github.com/brenw0rth/pync/archive/main.zip
```
</details>

> **Note**<br>
> By default, **pync** is installed without the **--exec** command.<br>
> To enable the **--exec** command, please install the **pync-exec** addon:

<details open>
<summary>Unix</summary>

```sh
pip install https://github.com/brenw0rth/pync-exec/archive/main.zip
```
</details>

<details>
<summary>Windows</summary>

```sh
py -m pip install https://github.com/brenw0rth/pync-exec/archive/main.zip
```
</details>

## Documentation
* [Getting Started](https://pync.readthedocs.io/en/latest/getting-started.html)
* [Options](https://pync.readthedocs.io/en/latest/options/index.html)
* [Examples](https://pync.readthedocs.io/en/latest/examples/index.html)
* [API Reference](https://pync.readthedocs.io/en/latest/reference/index.html)
* [Example Scripts](https://github.com/brenw0rth/pync/tree/main/examples)

## See Also
* [Netcat man page](https://helpmanual.io/man1/netcat/)

## License
See [LICENSE](https://github.com/brenw0rth/pync/blob/main/LICENSE)
