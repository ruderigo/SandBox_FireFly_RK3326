"""Interfaces shown the same way on every FireFly and Stump (proposal-interface-names v2),
and the radio's default frequency from the region.

Needs no radio and no network: Reticulum's own classes are asked how they print a name.
"""
import json, os, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, ".."))
import RNS
from firefly import ifaces, region, rnsconfig, lan
from firefly.settings import Settings, DEFAULTS

fails = 0
def check(ok, name, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    fails += 0 if ok else 1

# ------------------------------------------------------------------ the names we choose
check(lan.AUTO_NAME == "Local network", "the local network is named 'Local network'", lan.AUTO_NAME)
check(ifaces.RNODE == "RNode", "the radio is named 'RNode'")
check([ifaces.tcp_name(i) for i in range(3)] == ["TCP", "TCP 2", "TCP 3"], "TCP links are TCP, TCP 2, TCP 3")

cfg = rnsconfig.build_config(dict(DEFAULTS, tcp_peers=["hub.example:4242", "bad", "10.0.0.5:4965"]))
check("[[TCP]]" in cfg and "[[TCP 2]]" in cfg and "TCP peer" not in cfg and "[[TCP 3]]" not in cfg,
      "the Reticulum config names them so, counting only the usable ones", cfg)

# ------------------------------------------------------------------ what Reticulum then prints
from RNS.Interfaces.AutoInterface import AutoInterface
from RNS.Interfaces.TCPInterface import TCPClientInterface
from RNS.Interfaces.RNodeInterface import RNodeInterface
from firefly.radio import FireFlyRNode

def printed(cls, **attrs):
    i = cls.__new__(cls)                 # only the name is asked for: nothing is opened
    for k, v in attrs.items():
        setattr(i, k, v)
    return str(i)

check(printed(AutoInterface, name=ifaces.LOCAL_NETWORK) == "AutoInterface[Local network]", "AutoInterface[Local network]",
      printed(AutoInterface, name=ifaces.LOCAL_NETWORK))
got = printed(TCPClientInterface, name=ifaces.tcp_name(0), target_ip="hub.example", target_port=4242)
check(got == "TCPInterface[TCP/hub.example:4242]", "TCPInterface[TCP/host:port], the address once", got)
got = printed(FireFlyRNode, name=ifaces.RNODE)
check(got == "RNodeInterface[RNode]", "RNodeInterface[RNode]", got)

# ------------------------------------------------------------------ line 1, hidden rows, fields
for name, want in (("AutoInterface[Local network]", "Local network"), ("RNodeInterface[RNode]", "LoRa radio"),
                   ("TCPInterface[TCP/h:1]", "TCP"), ("TCPServerInterface[TCP/0.0.0.0:4242]", "TCP, listening"),
                   ("Shared Instance[rns/default]", "Shared instance"), ("KISSInterface[x]", "KISSInterface")):
    check(ifaces.label(name) == want, f"line 1 of {name}: {want}", ifaces.label(name))

for name in ("AutoInterfacePeer[wlan0/fe80::1]", "LocalInterface[37428]", "TCPInterface[Client on TCP/1.2.3.4:5]",
             "BackboneInterface[Client on x]", "WeaveInterfacePeer[x]", "I2PInterfacePeer[Connected peer to x]", "None", ""):
    check(ifaces.hidden({"name": name}), f"never shown: {name or '(no name)'}")
for name in ("AutoInterface[Local network]", "RNodeInterface[RNode]", "TCPInterface[TCP/h:1]", "Shared Instance[rns/default]"):
    check(not ifaces.hidden({"name": name}), f"shown: {name}")
# The same list as the installed rnstatus: if Reticulum changes it, this says so.
import inspect, RNS.Utilities.rnstatus as rnstatus
src = inspect.getsource(rnstatus)
check(all(f'name.startswith("{p}")' in src for p in ifaces.HIDDEN), "the hidden list is the installed rnstatus's")

f = ifaces.fields({"name": "AutoInterface[Local network]", "mode": 1, "peers": 2, "txb": 884, "rxb": 10880})
check(f == ["Peers: 2 reachable", "Traffic: ↑884 B  ↓10.88 KB"], "Peers and Traffic in rnstatus's words, sent first", f)
f = ifaces.fields({"name": "RNodeInterface[RNode]", "mode": 3, "txb": 0, "rxb": 0})
check(f[0] == "Mode: Access Point", "Mode shown when it isn't Full", f)
f = ifaces.fields({"name": "Shared Instance[rns/default]", "mode": 1, "clients": 1, "txb": 0, "rxb": 0})
check(f[0] == "Serving: 1 program", "Serving on the shared instance", f)

# ------------------------------------------------------------------ the region default
for tz, want in (("America/Toronto", 915), ("America/Los_Angeles", 915), ("US/Eastern", 915), ("America/Mexico_City", 915),
                 ("Europe/Paris", 868), ("Europe/London", 868), ("Atlantic/Canary", 868),
                 ("America/Sao_Paulo", 915), ("Asia/Tokyo", 915), ("Etc/UTC", 915), ("UTC", 915), ("", 915)):
    d = region.decide(timezone=tz)
    check(d["frequency"] == want * 1_000_000, f"time zone {tz or '(unset)'}: {want} MHz", d)
for tz in ("America/Sao_Paulo", "Asia/Tokyo", "Etc/UTC", "", "Europe/Moscow"):
    check(region.decide(timezone=tz)["region"] is None, f"{tz or '(unset)'} decides nothing (the fallback, with a note)")
check(region.decide(country="fr", timezone="America/Toronto")["frequency"] == 868_000_000, "a country code comes before the time zone")
check("Check the local rules" in region.describe(region.decide(timezone="UTC")), "an undecided default says to check the local rules")

tmp = tempfile.mkdtemp()
def fresh(tz):
    os.environ["TZ"] = tz
    path = os.path.join(tmp, tz.replace("/", "_") + ".json")
    return Settings(path), path

s, p = fresh("Europe/Paris")
check(s["radio"]["frequency"] == 868_000_000 and s["radio_region"]["source"] == "timezone", "a first start in Europe/Paris: 868 MHz", s["radio_region"])
check(s.stump_defaults()["frequency"] == 868_000_000, "and the Stump defaults there are on 868")
os.environ["TZ"] = "America/Toronto"
check(Settings(p)["radio"]["frequency"] == 868_000_000, "it is decided once: moving the time zone later changes nothing")
s, p = fresh("America/Toronto")
check(s["radio"]["frequency"] == 915_000_000 and s["radio_region"]["region"] == "na", "a first start in America/Toronto: 915 MHz")

# Settings from before this version (no radio_region): the frequency in use is kept.
old = os.path.join(tmp, "old.json")
json.dump({"radio": {"frequency": 915_000_000}}, open(old, "w"))
os.environ["TZ"] = "Europe/Paris"
s = Settings(old)
check(s["radio"]["frequency"] == 915_000_000 and s["radio_region"]["source"] == "kept", "an existing install keeps its frequency", s["radio_region"])
check(Settings(old)["radio_region"]["source"] == "kept", "and stays kept on the next start")

print("\n" + ("ALL PASS" if not fails else f"{fails} FAILED"))
sys.exit(1 if fails else 0)
