
import socket
import threading
import argparse
import json
import random
import time
import sys

# Uniform delay in the range [0.1, 0.5] ms == [0.0001, 0.0005] seconds
def rand_delay():
    return random.uniform(0.0001, 0.0005)

def proxy_once(client_conn, server_host, server_port):
    """Forward one request to time server and return a single response, with delays both ways."""
    # Receive one complete message (assume one JSON blob fits; small messages only)
    data = client_conn.recv(4096)
    if not data:
        return False
    # Delay before forwarding
    time.sleep(rand_delay())
    # Connect to time server for this request
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
        s2.connect((server_host, server_port))
        s2.sendall(data)
        resp = s2.recv(4096)
    # Delay before sending back
    time.sleep(rand_delay())
    client_conn.sendall(resp)
    return True

def handle_client(client_conn, addr, server_host, server_port):
    try:
        with client_conn:
            # For simplicity, treat each TCP connection as a single request/response cycle.
            proxy_once(client_conn, server_host, server_port)
    except Exception as e:
        sys.stderr.write(f"[network] error for {addr}: {e}\n")

def serve(nw_host, nw_port, server_host, server_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((nw_host, nw_port))
    s.listen(5)
    print(f"[network] listening on {nw_host}:{nw_port} -> forwarding to time_server {server_host}:{server_port}")
    try:
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr, server_host, server_port), daemon=True).start()
    finally:
        s.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="NW listen host")
    parser.add_argument("--port", type=int, default=5000, help="NW listen port")
    parser.add_argument("--server-host", default="127.0.0.1", help="time server host")
    parser.add_argument("--server-port", type=int, default=5001, help="time server port")
    args = parser.parse_args()
    serve(args.host, args.port, args["server_host"] if isinstance(args, dict) and "server_host" in args else args.server_host, args["server_port"] if isinstance(args, dict) and "server_port" in args else args.server_port)
