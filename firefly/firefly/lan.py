"""The handheld's own network, exactly as EmulationStation set it up.

FireFly never joins, scans or configures a network: the Wi-Fi name and
password are chosen in EmulationStation (or a cable is plugged in), and
FireFly uses whatever the handheld is on, like any app on a computer. It only
reads the state, and follows it while it runs:

* Reticulum's local discovery (AutoInterface, the way Sideband, NomadNet,
  MeshChat and other FireFlys find each other on a LAN) is attached at
  runtime, and attached again when the network comes up later or changes:
  Reticulum on its own only adopts the networks present when it starts.
* Stumps on the same network answer the `STUMP?` question on UDP 4244 with
  their name, LXMF address and web address; FireFly lists them.
* Internet peers (SETUP -> Internet/TCP peers) reconnect by themselves once
  there is a route out; NETWORK shows whether there is one.
"""
import json
import os
import socket
import subprocess
import threading
import time

import RNS

POLL_S = 5.0
STUMP_PORT = 4244
STUMP_SCAN_S = 60.0
STUMP_WAIT_S = 1.5
AUTO_NAME = "Local network (AutoInterface)"

# Never a LAN: loopback and the virtual interfaces of containers, VPNs and tunnels.
_IGNORED = ("lo", "dummy", "docker", "veth", "br-", "virbr", "tun", "tap", "ifb", "sit", "ip6", "wg", "p2p")


# ------------------------------------------------------------------ reading the state
def _netinfo():
    from RNS.Interfaces import netinfo
    return netinfo


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def interfaces():
    """[{name, ipv4, broadcast, link_local, wifi, up}] for the real network interfaces."""
    ni = _netinfo()
    out = []
    for name in ni.interfaces():
        if name.startswith(_IGNORED):
            continue
        try:
            addrs = ni.ifaddresses(name)
        except Exception:
            continue
        v4 = addrs.get(ni.AF_INET, [])
        v6 = addrs.get(ni.AF_INET6, [])
        state = _read(f"/sys/class/net/{name}/operstate")
        out.append({
            "name": name,
            "ipv4": v4[0].get("addr") if v4 else None,
            "broadcast": v4[0].get("broadcast") if v4 else None,
            "link_local": any(str(a.get("addr", "")).startswith("fe80:") for a in v6),
            "wifi": os.path.isdir(f"/sys/class/net/{name}/wireless") or name.startswith("wl"),
            "up": state in ("up", "unknown", "") and bool(v4 or v6),
        })
    return out


def default_route():
    """The interface the handheld's internet goes out on, or None."""
    for line in _read("/proc/net/route").splitlines()[1:]:
        f = line.split()
        if len(f) > 3 and f[1] == "00000000" and int(f[3], 16) & 2:   # destination 0.0.0.0, RTF_GATEWAY
            return f[0]
    return None


def ssid(ifname):
    """The Wi-Fi network's name, read-only (no root needed), or None."""
    for cmd in (["iwgetid", "-r", ifname], ["iw", "dev", ifname, "link"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode != 0:
            continue
        if cmd[0] == "iwgetid":
            name = r.stdout.strip()
            if name:
                return name
        else:
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    return line[5:].strip() or None
    return None


def snapshot():
    ifs = [i for i in interfaces() if i["up"]]
    for i in ifs:
        i["ssid"] = ssid(i["name"]) if i["wifi"] else None
    return {"ifaces": ifs, "internet": default_route()}


# ------------------------------------------------------------------ Stumps on the LAN
def _clean_stump(d):
    """A STUMP? answer, checked: untrusted data from anyone on the network."""
    if not isinstance(d, dict) or not d.get("stump"):
        return None
    lxmf = str(d.get("lxmf", ""))
    if len(lxmf) != 32 or any(c not in "0123456789abcdef" for c in lxmf.lower()):
        return None
    http = [str(u)[:80] for u in (d.get("http") or []) if isinstance(u, str) and u.startswith("http")][:4]
    here = d.get("here") if isinstance(d.get("here"), str) and str(d.get("here")).startswith("http") else ""
    return {"name": str(d.get("name", "Stump"))[:32], "lxmf": lxmf.lower(), "release": str(d.get("release", ""))[:32],
            "http": http, "here": here[:80] or (http[0] if http else ""), "seen": time.time()}


def find_stumps(targets, wait=STUMP_WAIT_S, port=STUMP_PORT):
    """Ask 'STUMP?' (Stump 1.0.0-beta.21+) at each target address; {lxmf: info}."""
    found = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.25)
        for t in targets:
            try:
                s.sendto(b"STUMP? v1", (t, port))
            except OSError:
                pass
        end = time.time() + wait
        while time.time() < end:
            try:
                data, _ = s.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                info = _clean_stump(json.loads(data[:2048].decode("utf-8", "replace")))
            except ValueError:
                info = None
            if info:
                found[info["lxmf"]] = info
    finally:
        s.close()
    return found


# ------------------------------------------------------------------ the manager
class LanManager:
    def __init__(self, core, lister=snapshot, stump_finder=find_stumps):
        self.core = core
        self.lister = lister
        self.stump_finder = stump_finder
        self.state = {"ifaces": [], "internet": None}
        self.auto = None               # the AutoInterface FireFly attached
        self.adopted = frozenset()     # the interfaces it was made for
        self.stumps = {}               # lxmf hex -> STUMP? answer
        self.last_scan = 0.0
        self.changes = 0               # network changes seen (for tests and the log)
        self.wake = threading.Event()
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True, name="firefly-lan").start()

    def stop(self):
        self.running = False
        self.wake.set()
        self._detach()

    def poke(self):
        """Settings changed or the user asked: look again now."""
        self.last_scan = 0.0
        self.wake.set()

    # ---------------------------------------------------------------- loop
    def _run(self):
        while self.running:
            try:
                self._tick()
            except Exception as e:          # the network must never take the app down
                RNS.log(f"LAN manager error: {e}", RNS.LOG_ERROR)
            self.wake.wait(POLL_S)
            self.wake.clear()

    def _key(self, st):
        return tuple(sorted((i["name"], i.get("ipv4"), i.get("ssid")) for i in st["ifaces"])), st["internet"]

    def _tick(self):
        st = self.lister()
        changed = self._key(st) != self._key(self.state)
        self.state = st
        if self.core.shared_instance:
            return                           # rnsd's config decides the interfaces
        want = frozenset(i["name"] for i in st["ifaces"] if i.get("link_local"))
        if not self.core.settings["auto_interface"] or not self.core.settings["managed_config"]:
            want = frozenset()       # switched off, or the user's own ~/.reticulum decides
        if want != self.adopted or (want and self.auto is not None and getattr(self.auto, "detached", False)):
            self._detach()
            if want:
                self._attach(want)
        if changed:
            self.changes += 1
            names = ", ".join(f"{i['name']} {i.get('ssid') or ''} {i.get('ipv4') or ''}".strip() for i in st["ifaces"])
            RNS.log(f"Network: {names or 'none'}; internet {'via ' + st['internet'] if st['internet'] else 'none'}")
            if st["ifaces"]:
                self.last_scan = 0.0
                try:
                    self.core.on_interface_online()     # announce on the new network, collect messages
                except Exception:
                    pass
            else:
                self.stumps = {}
        if any(i.get("ipv4") for i in st["ifaces"]) and time.time() - self.last_scan > STUMP_SCAN_S:
            self.last_scan = time.time()
            targets = {"255.255.255.255"} | {i["broadcast"] for i in st["ifaces"] if i.get("broadcast")}
            found = self.stump_finder(sorted(targets))
            for k, v in list(self.stumps.items()):
                if time.time() - v["seen"] > 3 * STUMP_SCAN_S:
                    del self.stumps[k]
            self.stumps.update(found)
        try:
            self.core.sync_web(self.stumps)            # chat with them over Wi-Fi
        except Exception as e:
            RNS.log(f"Stumps over Wi-Fi: {e}", RNS.LOG_WARNING)

    # ---------------------------------------------------------------- AutoInterface
    def _attach(self, names):
        from RNS.Interfaces.AutoInterface import AutoInterface
        try:
            iface = AutoInterface(RNS.Transport, {"name": AUTO_NAME})
            self.core.reticulum._add_interface(iface)
        except Exception as e:
            RNS.log(f"Local network discovery could not start: {e}", RNS.LOG_WARNING)
            return
        self.auto, self.adopted = iface, names
        # Reticulum finishes an AutoInterface after registering it; that waits for peering.
        threading.Thread(target=self._final_init, args=(iface,), daemon=True).start()
        RNS.log(f"Local network discovery on {', '.join(sorted(names))}")

    @staticmethod
    def _final_init(iface):
        try:
            iface.final_init()
        except Exception as e:
            RNS.log(f"Local network discovery: {e}", RNS.LOG_WARNING)

    def _detach(self):
        iface, self.auto, self.adopted = self.auto, None, frozenset()
        if iface is None:
            return
        for peer in list(getattr(iface, "spawned_interfaces", {}).values()):
            try:
                peer.detach()
                RNS.Transport.remove_interface(peer)
            except Exception:
                pass
        try:
            iface.detach()
        except Exception:
            pass
        try:
            RNS.Transport.remove_interface(iface)
        except Exception:
            pass

    # ---------------------------------------------------------------- for the screen
    def summary(self):
        """Lines for NETWORK: what the handheld is on, as EmulationStation set it."""
        st = self.state
        if not st["ifaces"]:
            return ["No network: join Wi-Fi in EmulationStation's settings (or plug in a cable).",
                    "FireFly keeps working over LoRa."]
        out = []
        for i in st["ifaces"]:
            kind = "Wi-Fi" if i["wifi"] else ("USB network" if i["name"].startswith(("usb", "enx")) else "Ethernet")
            what = f"{kind} {i['ssid']}" if i.get("ssid") else kind
            out.append(f"{what} ({i['name']}) {i.get('ipv4') or 'no IPv4'}")
        out.append("Internet: " + (f"yes, via {st['internet']}" if st["internet"] else "no (local network only)"))
        if not self.core.settings["auto_interface"]:
            out.append("Local discovery: off (SETUP)")
        elif self.auto is not None:
            peers = len(getattr(self.auto, "peers", {}) or {})
            out.append(f"Local discovery: on, {peers} Reticulum device(s) nearby")
        else:
            out.append("Local discovery: waiting for an IPv6 link")
        return out
