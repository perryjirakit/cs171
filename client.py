
import argparse
import json
import socket
import time
import csv
import math
import sys
from typing import Tuple

def now() -> float:
    return time.time()

class LocalClock:
    """
    Local clock with drift rho (unitless ratio). Uses base anchors (Rbase, Lbase).
    L(t) = Lbase + (R(t) - Rbase) * (1 + rho)
    """
    def __init__(self, rho: float):
        self.rho = rho
        rt = now()
        self.Rbase = rt
        self.Lbase = rt  # start with no offset
        self.last_sync_wall = rt

    def read(self) -> float:
        rt = now()
        return self.Lbase + (rt - self.Rbase) * (1.0 + self.rho)

    def sync_cristian(self, nw_host: str, nw_port: int) -> Tuple[float, float, float]:
        """
        Perform a Cristian sync via the NW proxy to the time server.
        Returns (server_time, rtt, offset_applied).
        """
        t0 = now()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((nw_host, nw_port))
            msg = {"type": "time_req"}
            s.sendall(json.dumps(msg).encode("utf-8"))
            data = s.recv(4096)
        t1 = now()

        resp = json.loads(data.decode("utf-8"))
        Ts = float(resp["server_time"])

        rtt = t1 - t0  # processing time is assumed zero at server
        # Cristian's estimate of server time at arrival: Ts + rtt/2
        est_server_at_arrival = Ts + rtt / 2.0

        # Our current real time is t1. We want L(t1) = est_server_at_arrival
        # Solve for new bases: set Rbase = t1, Lbase = est_server_at_arrival
        new_Rbase = t1
        new_Lbase = est_server_at_arrival

        # Compute current local time before adjustment to report applied offset
        before = self.read()
        self.Rbase = new_Rbase
        self.Lbase = new_Lbase
        self.last_sync_wall = t1
        after = self.read()

        return Ts, rtt, (after - before)

    def drift_error_bound(self) -> float:
        """Estimated absolute drift error since last sync from drift alone."""
        dt = now() - self.last_sync_wall
        return abs(self.rho) * dt

def run_client(d: int, epsilon_max: float, rho: float, nw_host: str, nw_port: int, out_csv: str):
    clk = LocalClock(rho=rho)

    # Immediately perform an initial sync to align with server at start
    try:
        Ts, rtt, off = clk.sync_cristian(nw_host, nw_port)
        print(f"[client] initial sync: rtt={rtt*1000:.3f} ms, offset_applied={off:.6f}s")
    except Exception as e:
        print(f"[client] WARNING: initial sync failed ({e}), continuing with unsynced clock.")

    # Decide when to re-sync. We keep the drift contribution safely below epsilon_max.
    # Simple policy: if drift_error_bound() >= 0.8 * epsilon_max, re-sync.
    end_time = now() + d

    # CSV writer
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["actual_time", "local_time"])

        next_record = math.floor(now()) + 1  # align records to next second boundary
        while now() < end_time:
            # Periodic drift check
            if clk.drift_error_bound() >= 0.8 * epsilon_max:
                try:
                    Ts, rtt, off = clk.sync_cristian(nw_host, nw_port)
                    print(f"[client] sync: rtt={rtt*1000:.3f} ms, offset_applied={off:.6f}s")
                except Exception as e:
                    print(f"[client] sync failed: {e}")

            # Record once per system second
            t = now()
            if t >= next_record:
                actual_time = t
                local_time = clk.read()
                # Print to 3 decimals (milliseconds) with comma delimiter, no extra spaces
                writer.writerow([f"{actual_time:.3f}", f"{local_time:.3f}"])
                next_record += 1

            # Sleep a bit to reduce busy-waiting
            time.sleep(0.01)

    print(f"[client] wrote CSV to {out_csv}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--d", type=int, required=True, help="duration to run (seconds)")
    p.add_argument("--epsilon", type=float, required=True, help="maximum tolerable error (seconds)")
    p.add_argument("--rho", type=float, required=True, help="clock drift ratio (unitless)")
    p.add_argument("--nw-host", default="127.0.0.1")
    p.add_argument("--nw-port", type=int, default=5000)
    p.add_argument("--out", default="output.csv")
    args = p.parse_args()
    run_client(args.d, args.epsilon, args.rho, args.nw_host, args.nw_port, args.out)
