# FireFly quick start

FireFly is a messenger for RK3326 handhelds (R36MAX, R36S): text and voice
notes over LoRa, Wi-Fi or the internet, with anyone on Reticulum (Sideband,
MeshChat, Nomad Network) and through LaBuche Stumps. This page gets you
going; [INSTALL.md](INSTALL.md) has every detail, [README.md](README.md)
everything FireFly does.

## What you need

- An RK3326 handheld running dArkOS, with Wi-Fi or USB Ethernet for the
  first install.
- For LoRa: a LoRa board flashed with RNode firmware, on the handheld's USB.
- Optional: USB-C headphones or a headset, for voice notes (and its mic, to
  record them).

## Install

1. Download `FireFly-RK3326-X.Y.Z.zip` from the
   [latest release](https://github.com/ruderigo/SandBox_FireFly_RK3326/releases/latest).
2. From your computer, copy it to the handheld:
   ```bash
   scp FireFly-RK3326-X.Y.Z.zip ark@r36max.local:~/
   ```
3. Install it (it keeps your identity and messages when you update):
   ```bash
   ssh -t ark@r36max.local 'mkdir -p ~/firefly-new && unzip -o ~/FireFly-RK3326-X.Y.Z.zip -d ~/firefly-new && bash ~/firefly-new/firefly/deploy/cleanup.sh && bash ~/firefly-new/firefly/deploy/install.sh && rm -rf ~/firefly-new ~/FireFly-RK3326-X.Y.Z.zip'
   ```
4. Reboot the handheld once after the first install.
5. Open **Ports → FireFly**.

## First start

1. **SETUP**: your display name, and the radio settings of your network
   (for Stumps: *Load Stump defaults*).
2. **NETWORK**: the radio shows **● online**; A announces you.
3. **PEERS**: people appear as they announce; A opens a chat.
4. **Back up your identity now**: the key file *is* your address, and
   nobody can recover it. From your computer:
   ```bash
   scp ark@r36max.local:/home/ark/.firefly/identity ~/firefly-identity-backup
   ```
   Keep that file private: anyone who has it can pose as you.

## The tabs

| Tab | What's there |
|---|---|
| CHATS | Your conversations with people |
| STUMPS | Every Stump FireFly knows: answers?, LoRa / Wi-Fi, hops, your room, verified, unread |
| PEERS | Everyone heard on the network |
| NETWORK | The radio, Wi-Fi, other links, propagation nodes |
| SETUP | You, the radio, sound, voice notes, the screen |

## The buttons

| Button | What it does |
|---|---|
| D-pad | Move. In a Stump: ←/→ its rooms, then its DMs |
| A | Open, select. In a chat: details, play a voice note, reply to a DM |
| B | Back |
| START | Write a message |
| X | Quick replies (in a chat), the tab's action (in a list) |
| Y | Menu: record a voice note, block, delete... |
| L1 / R1 | Switch tabs; in a chat, page up / back to the newest |
| SELECT + START | Quit |
| SELECT + R1 | Rotate the screen |

## Sound

| Sound | When | Change it |
|---|---|---|
| Voice notes | You press A on one; X in the recorder to hear yours first | — |
| Message sound (two short notes, 0.2 s) | A message from a person, or a DM through a Stump | SETUP → SOUND → *Message sound*: people and DMs, everything (Stump rooms too), off |

- **Where:** USB-C headphones or a USB headset when one is plugged in,
  otherwise the built-in speaker; SETUP → SOUND → *Plays on* says which.
- **Never:** key clicks, a start-up sound, the backlog that was waiting,
  or a sound over a voice note that's playing.
- **Volume:** the handheld's volume buttons.

## Voice notes

1. In a chat, Y → **Record a voice note** (through a Stump: *Voice note to
   <name>*, a private message).
2. A records; A again stops (15 s at most).
3. X to listen, Y to switch codec, A to send, B to throw it away.

It records from the USB headset's mic when plugged in (SETUP → SOUND →
*Records from*). Quality: Opus at 24 kbit/s when it fits; through a Stump
(16 KB per note), the best a note that long allows. Codec 2, the smallest,
for slow LoRa: SETUP → VOICE NOTES → *Send as*.

## Stumps

- **STUMPS** lists them; A opens one.
- Its rooms are pills under the header: ←/→ moves between them, and FireFly
  joins the room you stop on (`…` until the Stump says you're in).
- **DMs** (after the rooms) is its private messages: A on one replies.
- A Stump set to *hybrid* or *closed* asks you to verify: FireFly does
  `/auth` for you.

## Updating and help

- **Update:** repeat steps 2 and 3 of Install with the new zip; no reboot.
- **Something wrong:** [INSTALL.md → Troubleshooting](INSTALL.md#troubleshooting),
  and `bash ~/firefly/deploy/device_report.sh` on the handheld lists what
  it has (radio, sound tools, versions) to send to whoever helps you.
