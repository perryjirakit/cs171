#!/usr/bin/env python3
import socket
import threading
import time
import random

# ---- Proxy (NW) listen address ----
NW_HOST = "127.0.0.1"
NW_PORT = 5001

# ---- Upstream time server ----
TS_HOST = "127.0.0.1"
TS_PORT = 8090   # matches your time_server.py

# ---- Artificial one-way delay (seconds) ----
# Uniform in [0.1, 0.5] milliseconds
MIN_DELAY_S = 0.0001
MAX_DELAY_S = 0.0005

def _delay():
    time.sleep(random.uniform(MIN_DELAY_S, MAX_DELAY_S))

def handle_client(client_conn: socket.socket, client_addr):
    """
    For each client:
      - open a single TCP connection to the time server
      - forward one line at a time with delay both ways
      - close cleanly when either side closes
    """
    ts_sock = None
    try:
        # Connect upstream to Time Server
        ts_sock = socket.create_connection((TS_HOST, TS_PORT), timeout=2.0)
        ts_in = ts_sock.makefile("rb")
        ts_out = ts_sock.makefile("wb")

        cli_in = client_conn.makefile("rb")
        cli_out = client_conn.makefile("wb")

        while True:
            # Read exactly one line from client
            line = cli_in.readline()
            if not line:
                break  # client closed

            # Delay before forwarding to TS
            _delay()
            ts_out.write(line)
            ts_out.flush()

            # Read exactly one line from TS
            resp = ts_in.readline()
            if not resp:
                break  # TS closed; stop

            # Delay before sending back to client
            _delay()
            cli_out.write(resp)
            cli_out.flush()

    except Exception:
        # Silently drop on network issues; client will retry next sync
        pass
    finally:
        for s in (ts_sock, client_conn):
            try:
                if s:
                    s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                if s:
                    s.close()
            except Exception:
                pass

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((NW_HOST, NW_PORT))
        srv.listen(16)
        print(f"[NW] Listening on {NW_HOST}:{NW_PORT} → forwarding to {TS_HOST}:{TS_PORT}")
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
