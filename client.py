#!/usr/bin/env python3
import argparse
import json
import math
import socket
import time
from pathlib import Path

NW_HOST_DEFAULT = "127.0.0.1"
NW_PORT_DEFAULT = 5001

# ---------- Local clock with drift ----------
class DriftClock:
    """
    Local clock L(t) = Lbase + (R(t) - Rbase) * (1 + rho),
    where R(t) is real process time (Unix epoch seconds).
    """
    def __init__(self, rho: float):
        self.rho = float(rho)
        now = time.time()
        self.Lbase = now
        self.Rbase = now

    def now(self) -> float:
        R = time.time()
        return self.Lbase + (R - self.Rbase) * (1.0 + self.rho)

    def set(self, new_local_time: float):
        """Reset bases so that L(now) == new_local_time."""
        self.Rbase = time.time()
        self.Lbase = float(new_local_time)

# ---------- Cristian sync ----------
def cristian_sync(nw_host: str, nw_port: int) -> tuple[float, float]:
    """
    Perform one sync round via the NW proxy.
    Returns:
        (server_time, rtt_seconds)
    """
    t0 = time.time()
    req = {"type": "time_req"}
    data = (json.dumps(req) + "\n").encode("utf-8")

    with socket.create_connection((nw_host, nw_port), timeout=2.0) as sock:
        sock.sendall(data)
        f = sock.makefile("rb")
        line = f.readline()
        if not line:
            raise RuntimeError("Empty response from time server")
        resp = json.loads(line.decode("utf-8"))

    t2 = time.time()
    if resp.get("type") != "time_resp" or "server_time" not in resp:
        raise RuntimeError("Malformed response from time server")
    ts = float(resp["server_time"])
    rtt = t2 - t0
    return ts, rtt

def next_interval_seconds(epsilon_max: float, rtt: float, rho: float) -> float:
    """
    Keep error ≤ εmax:
      immediate post-sync error ≤ rtt/2
      drift after Δ seconds adds |rho|*Δ
      rtt/2 + |rho|*Δ ≤ εmax  =>  Δ ≤ (εmax - rtt/2)/|rho|
    """
    delta = rtt / 2.0
    margin = epsilon_max - delta
    if margin <= 0:
        # Network alone exceeds epsilon; retry very soon
        return 0.5
    if abs(rho) < 1e-18:
        # Essentially perfect local clock; still sync occasionally
        return min(60.0, margin / 1e-12)
    return max(0.5, margin / abs(rho))

def write_csv_row(csv_path: Path, actual_time: float, local_time: float, header_written: list):
    if not header_written[0]:
        csv_path.write_text("actual_time,local_time\n", encoding="utf-8")
        header_written[0] = True
    with csv_path.open("a", encoding="utf-8") as f:
        f.write(f"{actual_time:.3f},{local_time:.3f}\n")

def main():
    p = argparse.ArgumentParser(description="Cristian's algorithm client with drift and CSV logging.")
    p.add_argument("--d", type=int, required=True, help="Duration to run (seconds)")
    p.add_argument("--epsilon", type=float, required=True, help="Maximum tolerable error εmax (seconds)")
    p.add_argument("--rho", type=float, required=True, help="Clock drift ρ (e.g., 2e-6)")
    p.add_argument("--csv", type=str, default="output.csv", help="CSV output file")
    p.add_argument("--nw_host", type=str, default=NW_HOST_DEFAULT, help="Network proxy host")
    p.add_argument("--nw_port", type=int, default=NW_PORT_DEFAULT, help="Network proxy port")
    args = p.parse_args()

    clock = DriftClock(args.rho)
    csv_path = Path(args.csv)
    if csv_path.exists():
        csv_path.unlink()
    header_written = [False]

    start = time.time()
    end = start + args.d

    # Initial sync asap
    try:
        ts, rtt = cristian_sync(args.nw_host, args.nw_port)
        clock.set(ts + rtt / 2.0)
        sync_interval = next_interval_seconds(args.epsilon, rtt, args.rho)
    except Exception:
        sync_interval = 1.0  # try again soon if first sync fails

    next_sync_at = time.time() + sync_interval
    next_log_at = math.floor(time.time()) + 1  # log on whole-second ticks

    while time.time() < end:
        now_real = time.time()

        # 1 Hz logging on real time
        if now_real >= next_log_at:
            write_csv_row(csv_path, now_real, clock.now(), header_written)
            next_log_at += 1

        # Periodic resync based on ε, ρ, and observed RTT
        if now_real >= next_sync_at:
            try:
                ts, rtt = cristian_sync(args.nw_host, args.nw_port)
                clock.set(ts + rtt / 2.0)
                sync_interval = next_interval_seconds(args.epsilon, rtt, args.rho)
            except Exception:
                sync_interval = 1.0  # transient failure; retry soon
            next_sync_at = time.time() + sync_interval

        time.sleep(0.005)  # light idle

    # Final flush if we ended exactly on a tick
    now_real = time.time()
    if math.isclose(now_real, next_log_at, abs_tol=0.01):
        write_csv_row(csv_path, now_real, clock.now(), header_written)

if __name__ == "__main__":
    main()
