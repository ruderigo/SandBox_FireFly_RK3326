"""The handheld's own network, read-only, followed live.   python3 tests/run_lan.py"""
import json, os, socket, sys, tempfile, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from firefly import lan
from firefly.paths import Paths
from firefly.settings import Settings
from firefly.core import Core
from firefly.rnsconfig import build_config

ok = True
def check(cond, what):
    global ok
    print(("  PASS " if cond else "  FAIL ") + what, flush=True)
    ok = ok and bool(cond)
def wait(fn, secs):
    t = time.time()
    while time.time() - t < secs:
        if fn(): return True
        time.sleep(0.1)
    return False

print("reading the network")
snap = lan.snapshot()
check(isinstance(snap["ifaces"], list) and all("name" in i for i in snap["ifaces"]), f"snapshot: {[i['name'] for i in snap['ifaces']]}")
check(not any(i["name"] == "lo" for i in snap["ifaces"]), "loopback is never a network")
print(f"     internet via: {lan.default_route()}")
check(lan.ssid("no-such-if0") is None, "no Wi-Fi name for an interface that isn't Wi-Fi")

print("Stumps answering STUMP?")
good = {"stump": 1, "name": "macOS", "lxmf": "b9b7de41a6b23b7a6108eb76cce3e8dd", "release": "1.0.0-beta.50",
        "http": ["http://192.168.0.176/"], "here": "http://192.168.0.176/"}
check(lan._clean_stump(good)["here"] == "http://192.168.0.176/", "a Stump's card is read")
check(lan._clean_stump({**good, "lxmf": "zz"}) is None, "a card with a bad LXMF address is refused")
check(lan._clean_stump({**good, "http": ["javascript:x"], "here": "file:/x"})["here"] == "", "odd web addresses dropped")
check(lan._clean_stump({"name": "x"}) is None, "not a Stump: ignored")
srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); srv.bind(("127.0.0.1", 0)); port = srv.getsockname()[1]
def answer():
    data, addr = srv.recvfrom(64)
    if data.startswith(b"STUMP?"):
        srv.sendto(json.dumps(good).encode(), addr)
threading.Thread(target=answer, daemon=True).start()
found = lan.find_stumps(["127.0.0.1"], wait=1.0, port=port)
check(list(found) == [good["lxmf"]] and found[good["lxmf"]]["name"] == "macOS", "STUMP? asked and answered over UDP")

print("following the network live (a fake network, the real manager)")
tmp = tempfile.mkdtemp(); paths = Paths(tmp); paths.ensure()
s = Settings(paths.settings); s["share_instance"] = False; s["log_level"] = 2; s.save()
check("AutoInterface" not in build_config(s.data), "local discovery is no longer in the start-up config")
_start = lan.LanManager.start
lan.LanManager.start = lambda self: None          # the real one stays idle: we drive our own
core = Core(paths, log=lambda *a: None); core.start()
lan.LanManager.start = _start
net = {"ifaces": [], "internet": None}
attached, onlines = [], []
m = lan.LanManager(core, lister=lambda: json.loads(json.dumps(net)), stump_finder=lambda t: {good["lxmf"]: lan._clean_stump(good)})
m._attach = lambda names: (attached.append(set(names)), setattr(m, "auto", object()), setattr(m, "adopted", names))
real_detach = m._detach
m._detach = lambda: (setattr(m, "auto", None), setattr(m, "adopted", frozenset()))
core.on_interface_online = lambda: onlines.append(time.time())
core.lan = m
m._tick()
check(m.auto is None and m.summary()[0].startswith("No network"), "no network: says to join one in EmulationStation")
net = {"ifaces": [{"name": "wlan0", "ipv4": "192.168.0.167", "broadcast": "192.168.0.255", "link_local": True,
                   "wifi": True, "up": True, "ssid": "Maison"}], "internet": "wlan0"}
m._tick()
check(attached == [{"wlan0"}], "Wi-Fi joined in ES after start: local discovery attached live")
check(len(onlines) == 1, "...and FireFly announces itself on it")
check(good["lxmf"] in m.stumps, "...and lists the Stump that answered STUMP?")
summ = m.summary()
check(summ[0].startswith("Wi-Fi Maison (wlan0) 192.168.0.167") and "Internet: yes" in summ[1], f"shown: {summ[:2]}")
m._tick()
check(attached == [{"wlan0"}] and len(onlines) == 1, "nothing changed: nothing redone")
net["ifaces"][0]["ssid"] = "Stump-LaBuche"; net["ifaces"][0]["ipv4"] = "192.168.4.23"; net["internet"] = None
m._tick()
check(len(onlines) == 2 and "Internet: no" in " ".join(m.summary()), "another network chosen in ES: followed, no internet shown")
net["ifaces"].append({"name": "usb0", "ipv4": "10.77.0.2", "broadcast": "10.77.0.255", "link_local": True,
                      "wifi": False, "up": True, "ssid": None})
m._tick()
check(attached[-1] == {"wlan0", "usb0"}, "a USB network adapter plugged in: discovery covers it too")
check(any("USB network (usb0) 10.77.0.2" in l for l in m.summary()), "shown as a USB network adapter")
core.settings["auto_interface"] = False
m._tick()
check(m.auto is None, "local discovery switched off in SETUP: detached live, no restart")
core.settings["auto_interface"] = True; core.settings["managed_config"] = False
m._tick()
check(m.auto is None, "with the user's own ~/.reticulum, FireFly adds nothing")
core.settings["managed_config"] = True
net = {"ifaces": [], "internet": None}
m._tick()
check(m.auto is None and not m.stumps, "network gone: discovery detached, Stump list cleared")

print("a real AutoInterface attached and detached at runtime")
m2 = lan.LanManager(core, lister=lambda: {"ifaces": [], "internet": None}, stump_finder=lambda t: {})
m2._attach(frozenset({"eth0"}))
check(m2.auto is not None and m2.auto in __import__("RNS").Transport.interfaces, "registered with Reticulum")
m2._detach()
check(m2.auto is None and all(getattr(i, "name", "") != lan.AUTO_NAME or i.detached for i in __import__("RNS").Transport.interfaces),
      "removed again cleanly")
core.stop()
print("ALL PASSED" if ok else "SOME FAILED")
sys.stdout.flush(); os._exit(0 if ok else 1)
