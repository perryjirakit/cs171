
import socket
import threading
import argparse
import json
import time

def handle_client(conn, addr):
    try:
        with conn:
            data = conn.recv(4096)
            if not data:
                return
            # Parse request (but we don't really need fields; we just respond immediately)
            try:
                _ = json.loads(data.decode("utf-8"))
            except Exception:
                pass
            # Respond immediately with current UNIX epoch seconds (float)
            resp = {"type": "time_resp", "server_time": time.time()}
            conn.sendall(json.dumps(resp).encode("utf-8"))
    except Exception as e:
        # Keep the server robust in student environments
        sys.stderr.write(f"Error handling client {addr}: {e}\n")

def serve(host: str, port: int):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    print(f"[server] listening on {host}:{port}")
    try:
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    finally:
        s.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    serve(args.host, args.port)
