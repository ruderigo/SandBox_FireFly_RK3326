"""Which handheld system FireFly is on, and what that changes.

FireFly runs on two families of systems for RK3326 handhelds:

* **arkos4clone / dArkOS / ArkOS**: EmulationStation and its Ports menu, a
  games partition at /roms (and /roms2 on a second card) that a computer sees
  when the SD card is plugged in. Sound: FireFly picks the device itself (a
  USB sound device first, else the built-in chip).
* **RK3326 Linux** (github.com/ruderigo/RK3326_Linux): its own desktop and
  dock, no /roms; your files are on /data/ark (the card's data partition,
  shown by its Files window). Its sound service, rk-audiod, owns the routing:
  it writes /etc/asound.conf so that the "default" device is the USB headset
  while one is plugged in, else the built-in chip, shared through a mixer
  and switched between speaker and headphones as the jack says. There,
  FireFly plays and records through "default" and lets it decide.

Everything here only reads files: a test points ROOT at a pretend system.
"""
import json
import os

ROOT = ""                                   # "" on the handheld; a folder in tests
RK_AUDIOD_MARK = "# written by rk-audiod"   # the first line of the asound.conf it writes


def _p(path):
    return ROOT + path


def is_rk3326_linux():
    """RK3326 Linux: its dock reads apps from /usr/share/rk/apps."""
    return os.path.isdir(_p("/usr/share/rk/apps"))


def managed_audio():
    """True when RK3326 Linux's rk-audiod owns the sound routing (its
    asound.conf is in place): then "default" is the right device."""
    try:
        with open(_p("/etc/asound.conf"), encoding="utf-8", errors="replace") as f:
            return f.readline().startswith(RK_AUDIOD_MARK)
    except OSError:
        return False


def audio_status():
    """What rk-audiod decided ({"out": {"name", "usb"}, "mic": ..., "path": "SPK"|"HP"}), or {}."""
    try:
        with open(_p("/run/rk-audio/status"), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def default_label(kind):
    """A name for "default" on RK3326 Linux, from rk-audiod's status: kind "out" or "mic"."""
    st = audio_status()
    dev = st.get(kind) if isinstance(st.get(kind), dict) else None
    if not dev:
        return "system default (RK3326 Linux)"
    if dev.get("usb"):
        return "USB: %s (RK3326 Linux)" % dev.get("name", "?")
    if kind == "out":
        where = {"SPK": "speaker", "HP": "headphones"}.get(st.get("path"), "built-in")
        return "built-in, %s (RK3326 Linux)" % where
    return "built-in (RK3326 Linux)"


def data_roots():
    """Folders that a person sees from outside FireFly, most preferred first:
    the games partitions (/roms2, /roms) on arkos4clone, /data/ark on RK3326
    Linux. Only those that exist."""
    return [r for r in ("/roms2", "/roms", "/data/ark") if os.path.isdir(_p(r))]


def where_label(path):
    """A folder as a person knows it: "SD card /firefly-voice", "Data /firefly-voice"."""
    for root, name in (("/roms2/", "SD card (2nd) /"), ("/roms/", "SD card /"), ("/data/ark/", "Data /")):
        if path.startswith(_p(root)):
            return name + path[len(_p(root)):]
    return path
