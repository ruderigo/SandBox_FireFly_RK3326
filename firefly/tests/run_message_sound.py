"""The message sound: when it plays (SETUP's Message sound: people and DMs by
default, everything, or off), never for the backlog found on connecting or a
Stump's answer to our own command, never over a voice note, and on the same
output as voice notes (USB headphones when plugged in).
   python3 tests/run_message_sound.py"""
import os, sys, tempfile, time, wave
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from firefly import voice
from firefly.paths import Paths
from firefly.settings import Settings
from firefly.core import Core
from firefly.stumpweb import StumpWeb
ok = True
def check(c, w):
    global ok; print(("  PASS " if c else "  FAIL ") + w); ok = ok and bool(c)

t = tempfile.mkdtemp()
p = Paths(os.path.join(t, "ff")); p.ensure()
s = Settings(p.settings); s["radio"]["enabled"] = False; s["auto_interface"] = False; s["share_instance"] = False; s.save()
c = Core(p, log=lambda *a: None)

# -- when ----------------------------------------------------------------------
check(c.settings.get("message_sound", "people") == "people", "default: people and DMs")
for kind, want in (("person", True), ("dm", True), ("room", False)):
    c.chime_due = 0
    check(c.notify(kind) == want and bool(c.chime_due) == want, f"people and DMs: a {kind} message {'sounds' if want else 'is quiet'}")
c.settings["message_sound"] = "all"
check(c.notify("room"), "everything: a Stump room's line too")
c.settings["message_sound"] = "off"
c.chime_due = 0
check(not c.notify("person") and not c.notify("dm") and not c.chime_due, "off: nothing")
c.settings["message_sound"] = "people"

# -- a Stump over Wi-Fi: news, not its backlog -------------------------------------
stp = "a8e7c0e088fc474c34360e91059be857"
c.store.upsert_peer(stp, "lxmf", name="LaBuche", stump="LaBuche", stump_ver="1.0.0-beta.87")
w = StumpWeb(c, {"lxmf": stp, "name": "LaBuche", "here": "http://127.0.0.1:9"})
w.nick, w.room = "R36-Operator", "lora-mesh"
w._fetch_voice = lambda mid, v: {}
c.chime_due = 0
w._store({"id": 1, "kind": "dm", "nick": "zoe", "text": "from before"}, news=False)
check(not c.chime_due, "a DM in the backlog it found as it connected: quiet")
w._store({"id": 2, "kind": "dm", "nick": "zoe", "text": "psst"})
check(c.chime_due, "a new DM over Wi-Fi: sounds")
c.chime_due = 0
w._store({"id": 3, "kind": "msg", "nick": "alice", "text": "hi room"})
check(not c.chime_due, "a room line, people and DMs: quiet")

# -- the sound itself ----------------------------------------------------------------
pl = voice.Player(log=lambda *a: None)
wav = pl.chime_wav()
with wave.open(wav) as wf:
    secs = wf.getnframes() / wf.getframerate()
check(0.15 < secs < 0.3, f"a short sound ({secs:.2f} s), made once")
asound = os.path.join(t, "asound"); os.makedirs(os.path.join(asound, "card1", "pcm0p")); os.makedirs(os.path.join(asound, "card0", "pcm0p"))
with open(os.path.join(asound, "cards"), "w") as f:
    f.write(" 0 [rk817          ]: rk817-codec - rockchip,rk817-codec\n 1 [Device         ]: USB-Audio - USB-C Headset\n")
bindir = os.path.join(t, "bin"); os.makedirs(bindir)
with open(os.path.join(bindir, "aplay"), "w") as f:
    f.write("#!/bin/sh\necho \"$@\" >> %s/aplay.log\n" % t)
os.chmod(os.path.join(bindir, "aplay"), 0o755)
os.environ["PATH"] = bindir + os.pathsep + os.environ["PATH"]
real_pick = voice.pick_output
voice.pick_output = lambda asound_=None: real_pick(asound)
check(pl.chime() == "USB: USB-C Headset", "played on USB headphones when plugged in ...")
time.sleep(0.3)
check("-D plughw:1,0" in open(os.path.join(t, "aplay.log")).read(), "... with aplay -D plughw:1,0")
os.remove(os.path.join(asound, "cards"))
check(pl.chime() == "built-in", "otherwise the built-in speaker")
pl.playing_id = 7; pl.busy = lambda: True
check(pl.chime() is None, "never over a voice note that's playing")
print("all passed" if ok else "FAILURES")
os._exit(0 if ok else 1)
