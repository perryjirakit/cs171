import socket
import threading
import time
import random

# NW proxy address
HOST = "127.0.0.1"
PORT = 5001

# Time server address
TS_HOST = "127.0.0.1"
TS_PORT = 8090

def handle_client(conn, addr):
    client_req = conn.recv(1024)
    # outgoing delay
    time.sleep(random.uniform(0.0001, 0.0005))

    with socket.create_connection((TS_HOST, TS_PORT), timeout=2.0) as ts_sock:
        ts_sock.sendall(client_req)
        ts_file = ts_sock.makefile("rb")
        ts_resp = ts_file.readline()
        if not ts_resp:
            ts_resp = b""

    # incoming delay
    time.sleep(random.uniform(0.0001, 0.0005))
    conn.sendall(ts_resp)
    conn.close()


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print("Network proxy is listening...")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
