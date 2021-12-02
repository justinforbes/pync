# pync
arbitrary TCP and UDP connections and listens ([Netcat](https://manpages.debian.org/testing/netcat-openbsd/nc.1.en.html) for Python).

## Description
pync is based on the [nc](https://manpages.debian.org/testing/netcat-openbsd/nc.1.en.html) (or [netcat](https://manpages.debian.org/testing/netcat-openbsd/nc.1.en.html)) utility,
though not yet as fully featured.</br>
It can open TCP connections, send UDP packets,
listen on arbitrary TCP and UDP ports and even
perform a simple port scan.

Common uses include:
* Interactive client/server communication
* Remote file transfer (upload/download)
* Port scanning
* Network chat
* Relaying/proxying network data
* Executing commands over the network

See the [Examples](#examples) section below for more.

## Installation
1. Install [Python](https://www.python.org/) if not already installed (version 2.7 or higher).

2. Use Python's pip command to install pync straight from github:
   ```sh
   pip install https://github.com/brenw0rth/pync/archive/main.zip
   ```

## Examples
<details>
<summary>Using pync from the command line</summary>

---
To use pync from the command line, you can use the pync command.<br/>
Create a TCP server with the "-l" option to listen for incoming connections:
   ```sh
   pync -l localhost 8000
   ```
You can also run pync as a module with Python.<br/>
Run the following command in a separate terminal window to connect to the server:
   ```sh
   python -m pync localhost 8000
   ```
To list all available options for the pync command, use the "-h" option:
   ```sh
   pync -h
   ```
</details>

<details>
<summary>Using pync inside a Python script</summary>

---
You can import pync into your own Python scripts too.<br/>
Here's an example that creates a local TCP server using the pync function:
   ```py
   # server.py
   from pync import pync
   with pync('-l localhost 8000') as nc:
       nc.run()
   ```
In a separate script, we can use the same pync function to connect to the server:
   ```py
   # client.py
   from pync import pync
   with pync('localhost 8000') as nc:
       nc.run()
   ```

</details>

<details>
<summary>Transfering files</summary>
</details>

<details>
<summary>Scanning for open ports</summary>
</details>

<details>
<summary>Relaying network data</summary>
</details>

<details>
<summary>Executing commands over the network</summary>
</details>

<details>
<summary>Simple network chat</summary>
</details>

<details>
<summary>Reverse/bind shell</summary>
</details>
