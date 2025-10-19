#!/usr/bin/env python3
import socket
import threading
import json
import time

HOST = "127.0.0.1"
PORT = 8090

def handle_client(conn, addr):
    data = conn.recv(1024)
    resp = {"type": "time_resp", "server_time": time.time()}
    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
    conn.close()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print("Server is listening...")

    while True:
        conn, addr = s.accept()
        # start a new thread for each client
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
