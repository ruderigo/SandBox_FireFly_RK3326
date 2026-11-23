"""FireFly: a gamepad-driven Reticulum / LXMF messenger for RK3326 handhelds."""
# The version ends in -b.<BUILD>: the SandBox_Stump_On build (Stump
# 1.0.0-beta.<BUILD>) this FireFly was tested against, as the handheld's Stump
# does (2.7.5-b.88). Written out in full: the release workflow, the RK3326
# Provisioner and RK3326 Linux's rk-apps read it from this line as text.
__version__ = "0.9.16-b.88"
BUILD = 88                                  # tests/run_version.py: must match the -b.NN above
STUMP_RELEASE = f"1.0.0-beta.{BUILD}"
VERSION_LABEL = __version__
APP_NAME = "FireFly"
