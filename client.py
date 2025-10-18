import argparse
import json
import math
import socket
import time
from pathlib import Path

def local_clock(rho: float):
    Lbase = time.time()
    Rbase = Lbase

    def now():
        R = time.time()
        return Lbase + (R - Rbase) * (1.0 + rho)

    def set_to(t_new: float):
        nonlocal Lbase, Rbase
        Rbase = time.time()
        Lbase = t_new

    return now, set_to

def cristian_sync(now, set_to, nw_host: str, nw_port: int) -> float:
    t0 = time.time()
    with socket.create_connection((nw_host, nw_port), timeout=2.0) as s:
        s.sendall(b'{"type":"time_req"}\n')
        line = s.makefile("rb").readline()
        if not line:
            raise RuntimeError("Empty time response")

    t2 = time.time()
    resp = json.loads(line.decode("utf-8"))
    if resp.get("type") != "time_resp" or "server_time" not in resp:
        raise RuntimeError("Malformed time response")

    Ts = float(resp["server_time"])
    rtt = t2 - t0
    # Estimate server time at receipt and set local clock to that
    set_to(Ts + rtt / 2.0)
    return rtt

def generate_csv(now, set_to, duration: int, epsilon: float, rho: float,
                 csv_path: Path, nw_host: str, nw_port: int):
    if csv_path.exists():
        csv_path.unlink()
    header_written = False

    end_at = time.time() + duration

    # First sync ASAP (if it fails, we’ll retry soon)
    try:
        rtt = cristian_sync(now, set_to, nw_host, nw_port)
    except Exception:
        rtt = 0.0  # fallback so we try again quickly

    # compute initial next-sync time
    def next_interval(eps, rtt_val, rho_val):
        delta_net = rtt_val / 2.0
        margin = eps - delta_net
        if margin <= 0:
            return 0.5
        if abs(rho_val) < 1e-18:
            return min(60.0, margin / 1e-12)
        return max(0.5, margin / abs(rho_val))

    sync_interval = next_interval(epsilon, rtt, rho)
    next_sync_at = time.time() + sync_interval
    next_log_at = math.floor(time.time()) + 1  # 1 Hz logging on real time

    while time.time() < end_at:
        now_real = time.time()

        # Log once per real second
        if now_real >= next_log_at:
            if not header_written:
                csv_path.write_text("actual_time,local_time\n", encoding="utf-8")
                header_written = True
            with csv_path.open("a", encoding="utf-8") as f:
                f.write(f"{now_real:.3f},{now():.3f}\n")
            next_log_at += 1

        # Perform sync when due
        if now_real >= next_sync_at:
            try:
                rtt = cristian_sync(now, set_to, nw_host, nw_port)
                sync_interval = next_interval(epsilon, rtt, rho)
            except Exception:
                sync_interval = 1.0  # retry soon on failure
            next_sync_at = time.time() + sync_interval

        time.sleep(0.005)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--d", type=int, required=True, help="Duration to run (seconds)")
    ap.add_argument("--epsilon", type=float, required=True, help="Max tolerable error ε (seconds)")
    ap.add_argument("--rho", type=float, required=True, help="Clock drift ρ (e.g., 2e-6)")
    ap.add_argument("--csv", type=str, default="output.csv", help="CSV output path")
    ap.add_argument("--nw_host", type=str, default="127.0.0.1")
    ap.add_argument("--nw_port", type=int, default=5001)
    args = ap.parse_args()

    now, set_to = local_clock(args.rho)
    generate_csv(now, set_to, args.d, args.epsilon, args.rho,
                 Path(args.csv), args.nw_host, args.nw_port)
