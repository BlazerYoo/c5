#!/usr/bin/env python3
"""
bridge_container.py — Unix socket listener that forwards to the TCP host bridge.
Replaces: setsid socat UNIX-LISTEN:SOCK_PATH,mode=600,fork TCP:HOST:PORT
Run inside the container via entrypoint.sh.

Environment variables:
  BRIDGE_SOCK_PATH  — Unix socket path to create (required)
  BRIDGE_TCP_HOST   — TCP host to connect to (default: host.docker.internal)
  BRIDGE_PORT       — TCP port (default: 9229)
"""
import os
import socket
import sys
import threading

SOCK_PATH = os.environ["BRIDGE_SOCK_PATH"]
TCP_HOST = os.environ.get("BRIDGE_TCP_HOST", "host.docker.internal")
TCP_PORT = int(os.environ.get("BRIDGE_PORT", "9229"))


def log(msg):
    print(f"[bridge-container] {msg}", file=sys.stderr, flush=True)


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


def handle_client(unix_conn: socket.socket):
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp.connect((TCP_HOST, TCP_PORT))
    except OSError as e:
        log(f"Failed to connect to {TCP_HOST}:{TCP_PORT}: {e}")
        unix_conn.close()
        return

    t1 = threading.Thread(target=forward, args=(unix_conn, tcp), daemon=True)
    t2 = threading.Thread(target=forward, args=(tcp, unix_conn), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    unix_conn.close()
    tcp.close()


def main():
    # Detach from the terminal's process group so Ctrl+C doesn't kill this bridge.
    # Mirrors the `setsid` wrapper used with socat in the original.
    os.setsid()

    # Remove stale socket from a previous run
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCK_PATH)
    os.chmod(SOCK_PATH, 0o600)
    server.listen(10)

    log(f"Listening on Unix socket {SOCK_PATH}")
    log(f"Forwarding to TCP {TCP_HOST}:{TCP_PORT}")

    while True:
        conn, _ = server.accept()
        t = threading.Thread(target=handle_client, args=(conn,), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
