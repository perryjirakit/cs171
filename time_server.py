#!/usr/bin/env python3
import socket
import threading
import json
import time

HOST = "127.0.0.1"
PORT = 8090   # Make sure your network.py forwards to this port

def handle_client(conn: socket.socket, addr):
    try:
        f_in = conn.makefile("rb")
        f_out = conn.makefile("wb")
        while True:
            line = f_in.readline()
            if not line:
                break  # client closed the connection
            # We ignore request contents; just return current Unix time
            now = time.time()
            resp = {"type": "time_resp", "server_time": now}
            f_out.write((json.dumps(resp) + "\n").encode("utf-8"))
            f_out.flush()
    finally:
        try:
            conn.close()
        except Exception:
            pass

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"[TS] Listening on {HOST}:{PORT}")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
