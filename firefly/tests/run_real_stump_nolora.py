"""FireFly on Wi-Fi against a real Stump with no LoRa radio (Stump 1.0.0-beta.57+:
"No LoRa on mesh"): #lora-mesh refuses it with the token '⊘ #lora-mesh no-lora',
FireFly reads it as a refusal and shows it as one sentence, and it chats in #main.

Set up the Stump once (from a SandBox_Stump_On checkout), as for run_real_stump.py
but with "the heltec": "None":
    python3 provisioner.py --pc /path/to/StumpNoLora --answers b.json
Then:
    STUMP_DIR_NO_LORA=/path/to/StumpNoLora python3 tests/run_real_stump_nolora.py

From Stump 1.0.0-beta.62 it also makes a Wi-Fi room with /create (the Stump's
/admin password: STUMP_ADMIN_PASSWORD, default test-pass-1) and reads /rooms.

Skipped (exit 0) when STUMP_DIR_NO_LORA isn't set.
"""
import os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

STUMP_DIR = os.environ.get("STUMP_DIR_NO_LORA")
if not STUMP_DIR:
    print("  (STUMP_DIR_NO_LORA not set: no real Stump to test against, skipped)")
    sys.exit(0)

from firefly.paths import Paths
from firefly.settings import Settings
from firefly.core import Core
from firefly import stump, lan

ok = True
def check(cond, what):
    global ok
    print(("  PASS " if cond else "  FAIL ") + what, flush=True)
    ok = ok and bool(cond)
def wait(fn, secs):
    t = time.time()
    while time.time() - t < secs:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

py = os.path.join(STUMP_DIR, "venv", "bin", "python")
log = open(os.path.join(tempfile.mkdtemp(), "stump.log"), "w")
node = subprocess.Popen([py if os.path.exists(py) else sys.executable, "stump_pc.py"], cwd=STUMP_DIR,
                        stdout=log, stderr=subprocess.STDOUT)
print("Stump started, log:", log.name, flush=True)

tmp = tempfile.mkdtemp(); paths = Paths(tmp); paths.ensure()
s = Settings(paths.settings); s["auto_interface"] = False; s["share_instance"] = False
s["display_name"] = "R36 Tester"; s["log_level"] = 2; s.save()
core = Core(paths, log=lambda *a: None); core.start()
core.radio.port_lister = lambda: []              # no radio on FireFly's side either: Wi-Fi only
try:
    found = {}
    check(wait(lambda: found.update(lan.find_stumps(["127.0.0.1", "255.255.255.255"], wait=2.0)) or found, 60),
          "the Stump answers STUMP? on the LAN")
    node_hex = next(iter(found), None)
    if not node_hex:
        raise SystemExit
    print(f"     {found[node_hex].get('name')} {found[node_hex].get('http')}", flush=True)
    core.lan.poke()
    check(wait(lambda: core.web.get(node_hex) is not None and core.web[node_hex].online, 60),
          "greeted the Stump over Wi-Fi (/hello, both sides signed)")

    def lines():
        return [it for m in core.store.messages(node_hex) if not m["outgoing"]
                for it in stump.parse_message(m["content"], m["title"] or "")]

    core.send(node_hex, "/join #lora-mesh")
    check(wait(lambda: any(it["kind"] == "refused" and it["room"] == "lora-mesh" and it["tier"] == "no-lora"
                           for it in lines()), 30),
          "/join #lora-mesh refused: '⊘ #lora-mesh no-lora' (No LoRa on mesh)")
    ref = next((it for it in lines() if it["kind"] == "refused"), None)
    if ref:
        print(f"     the Stump said: {ref['text']}", flush=True)
    # Stump 1.0.0-beta.62: a room with a scope (its /admin password), then /rooms says where it goes.
    pw = os.environ.get("STUMP_ADMIN_PASSWORD", "test-pass-1")
    core.send(node_hex, "/create %s #quiz -wifi" % pw)
    time.sleep(3)
    core.send(node_hex, "/rooms")
    check(wait(lambda: any(it["kind"] == "room" and it["room"] == "quiz" and it["scope"] == "wifi" for it in lines()), 30),
          "/create ... #quiz -wifi, then /rooms: #quiz read as a Wi-Fi room (beta.62)")
    for it in lines():
        if it["kind"] == "room":
            print(f"     #{it['room']} ·{it['count']} scope={it['scope']} topic={it['topic']!r}", flush=True)
    mid = core.send(node_hex, "hello in main")
    check(wait(lambda: core.store.message(mid)["state"] == "delivered" and core.store.message(mid)["method"] == "wifi", 20),
          "a line in #main over Wi-Fi: delivered")
finally:
    core.stop()
    node.terminate()
    try:
        node.wait(10)
    except subprocess.TimeoutExpired:
        node.kill()
    log.close()
print("ALL PASSED" if ok else "SOME FAILED")
sys.stdout.flush(); os._exit(0 if ok else 1)
