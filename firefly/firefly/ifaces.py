"""How an interface is shown: two lines, the second one Reticulum's own.

proposal-interface-names v2 (28 Nov 2026), the same on every FireFly and Stump:

* Line 1, for everyone: a plain label by type ("Local network", "LoRa radio", "TCP").
* Line 2, small and grey: the interface exactly as `rnstatus` prints it. We choose only the
  name inside the brackets (the NAMES below); Reticulum writes the rest.
* The rows `rnstatus` hides unless asked for all are never shown.
"""
import RNS

# The names we give our interfaces. Reticulum then prints AutoInterface[Local network],
# RNodeInterface[RNode], TCPInterface[TCP/host:4242].
LOCAL_NETWORK = "Local network"
RNODE = "RNode"


def tcp_name(n):
    """The n-th TCP link (from 0): TCP, TCP 2, TCP 3…"""
    return "TCP" if n == 0 else f"TCP {n + 1}"


# What Reticulum spawns per neighbour or per connected program: rnstatus's own list
# (RNS/Utilities/rnstatus.py, Reticulum 1.6.1). Recheck it when the Reticulum version changes.
HIDDEN = ("LocalInterface[", "TCPInterface[Client", "BackboneInterface[Client on",
          "AutoInterfacePeer[", "WeaveInterfacePeer[", "I2PInterfacePeer[Connected peer")


def hidden(stat):
    name = str(stat.get("name") or "")
    if not name or name == "None":
        return True                  # a row with no name is never one of ours to show
    if name.startswith(HIDDEN):
        return True
    return name.startswith("I2PInterface[") and stat.get("i2p_connectable") is False


_LABELS = (("AutoInterface[", "Local network"), ("RNodeInterface[", "LoRa radio"),
           ("RNodeMultiInterface[", "LoRa radio"), ("TCPServerInterface[", "TCP, listening"),
           ("TCPInterface[", "TCP"), ("Shared Instance[", "Shared instance"))


def label(name):
    """Line 1: what it is in plain words. An unknown type keeps Reticulum's word for it."""
    name = str(name or "")
    for prefix, text in _LABELS:
        if name.startswith(prefix):
            return text
    return name.split("[", 1)[0] or "?"


# rnstatus's words for Interface.mode.
MODES = {0x01: "Full", 0x02: "Point-to-Point", 0x03: "Access Point", 0x04: "Roaming",
         0x05: "Boundary", 0x06: "Gateway"}


def fields(stat):
    """The lines under an interface, in rnstatus's words and order: Mode (only when it isn't
    Full), Peers or Serving, Traffic (sent first)."""
    name = str(stat.get("name") or "")
    out = []
    shared = name.startswith("Shared Instance[")
    mode = MODES.get(stat.get("mode"))
    if mode and mode != "Full" and not shared:
        out.append(f"Mode: {mode}")
    if shared and stat.get("clients") is not None:
        n = int(stat["clients"])
        out.append(f"Serving: {n} program{'' if n == 1 else 's'}")
    elif stat.get("peers") is not None:
        out.append(f"Peers: {int(stat['peers'])} reachable")
    out.append(f"Traffic: ↑{RNS.prettysize(stat.get('txb') or 0)}  ↓{RNS.prettysize(stat.get('rxb') or 0)}")
    return out
