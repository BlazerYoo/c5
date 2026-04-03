#!/usr/bin/env python3
"""
bridge_host.py — TCP server that forwards connections to the Chrome NMH Unix socket.
Replaces bridge-host.js. Run this on the host machine.

Environment variables:
  BRIDGE_USER  — username for socket dir (default: current user)
  BRIDGE_PORT  — TCP port to listen on (default: 9229)
  BRIDGE_HOST  — TCP bind address (default: 0.0.0.0)
"""
import getpass
import os
import socket
import sys
import threading

SOCK_DIR = f"/tmp/claude-mcp-browser-bridge-{os.environ.get('BRIDGE_USER', getpass.getuser())}"
TCP_PORT = int(os.environ.get("BRIDGE_PORT", "9229"))
TCP_HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")


def log(msg):
    print(f"[bridge-host] {msg}", file=sys.stderr, flush=True)


def find_sock():
    try:
        files = [f for f in os.listdir(SOCK_DIR) if f.endswith(".sock")]
        if not files:
            return None
        files.sort()
        return os.path.join(SOCK_DIR, files[-1])
    except OSError:
        return None


def forward(src: socket.socket, dst: socket.socket):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle_client(tcp_conn: socket.socket, addr: str):
    sock_path = find_sock()
    if not sock_path:
        log(f"TCP client {addr} connected but no NMH socket in {SOCK_DIR}")
        tcp_conn.close()
        return

    log(f"TCP client {addr} -> NMH {sock_path}")

    nmh = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        nmh.connect(sock_path)
    except OSError as e:
        log(f"Failed to connect to NMH socket: {e}")
        tcp_conn.close()
        return

    log("Connected to NMH socket")

    t1 = threading.Thread(target=forward, args=(tcp_conn, nmh), daemon=True)
    t2 = threading.Thread(target=forward, args=(nmh, tcp_conn), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    tcp_conn.close()
    nmh.close()
    log(f"TCP client {addr} disconnected")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(10)

    log(f"Listening on {TCP_HOST}:{TCP_PORT}")
    log(f"NMH socket dir: {SOCK_DIR}")
    sock = find_sock()
    if sock:
        log(f"Found NMH socket: {sock}")
    else:
        log("No NMH socket yet, will check on each connection")

    while True:
        conn, addr = server.accept()
        addr_str = f"{addr[0]}:{addr[1]}"
        t = threading.Thread(target=handle_client, args=(conn, addr_str), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
