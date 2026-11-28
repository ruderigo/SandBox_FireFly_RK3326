"""The radio's default frequency, from where the device is.

One rule for every FireFly and Stump (proposal-interface-names v2, question 4, decided
28 Nov 2026): North America defaults to 915 MHz, Europe to 868 MHz. Where the device is
comes from a country code when the system has one (a phone's network or SIM), else from
the time zone. Never from the language. A time zone that is unset, UTC, or outside those
two regions decides nothing: the default stays 915 MHz, and the screen says to check the
local rules.

This only picks a default for a radio that has never been set up. A frequency somebody
set is never changed by it.

The same file is used by FireFly RK3326, FireFly Android and the Stump; keep them the same.
"""
import os

FREQ = {"na": 915_000_000, "eu": 868_000_000}
FALLBACK = "na"                      # what an undecided device gets: 915 MHz
LABEL = {"na": "North America", "eu": "Europe"}

_NA_COUNTRIES = frozenset("US CA MX".split())
_EU_COUNTRIES = frozenset(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE "
    "GB NO IS LI CH GG JE IM AD MC SM VA GI".split())

# Time zones of those countries (tzdata's zone.tab and its older link names).
_NA_ZONES = frozenset((
    "America/Adak America/Anchorage America/Atikokan America/Atka America/Bahia_Banderas "
    "America/Blanc-Sablon America/Boise America/Cambridge_Bay America/Cancun America/Chicago "
    "America/Chihuahua America/Ciudad_Juarez America/Coral_Harbour America/Creston America/Dawson "
    "America/Dawson_Creek America/Denver America/Detroit America/Edmonton America/Ensenada "
    "America/Fort_Nelson America/Fort_Wayne America/Glace_Bay America/Goose_Bay America/Halifax "
    "America/Hermosillo America/Indiana/Indianapolis America/Indiana/Knox America/Indiana/Marengo "
    "America/Indiana/Petersburg America/Indiana/Tell_City America/Indiana/Vevay "
    "America/Indiana/Vincennes America/Indiana/Winamac America/Indianapolis America/Inuvik "
    "America/Iqaluit America/Juneau America/Kentucky/Louisville America/Kentucky/Monticello "
    "America/Knox_IN America/Los_Angeles America/Louisville America/Matamoros America/Mazatlan "
    "America/Menominee America/Merida America/Metlakatla America/Mexico_City America/Moncton "
    "America/Monterrey America/Montreal America/New_York America/Nipigon America/Nome "
    "America/North_Dakota/Beulah America/North_Dakota/Center America/North_Dakota/New_Salem "
    "America/Ojinaga America/Pangnirtung America/Phoenix America/Rainy_River America/Rankin_Inlet "
    "America/Regina America/Resolute America/Santa_Isabel America/Shiprock America/Sitka "
    "America/St_Johns America/Swift_Current America/Thunder_Bay America/Tijuana America/Toronto "
    "America/Vancouver America/Whitehorse America/Winnipeg America/Yakutat America/Yellowknife "
    "Canada/Atlantic Canada/Central Canada/Eastern Canada/Mountain Canada/Newfoundland "
    "Canada/Pacific Canada/Saskatchewan Canada/Yukon Mexico/BajaNorte Mexico/BajaSur "
    "Mexico/General Pacific/Honolulu Pacific/Johnston US/Alaska US/Aleutian US/Arizona US/Central "
    "US/East-Indiana US/Eastern US/Hawaii US/Indiana-Starke US/Michigan US/Mountain US/Pacific "
).split())
_EU_ZONES = frozenset((
    "Africa/Ceuta Asia/Famagusta Asia/Nicosia Atlantic/Azores Atlantic/Canary Atlantic/Jan_Mayen "
    "Atlantic/Madeira Atlantic/Reykjavik Europe/Amsterdam Europe/Andorra Europe/Athens "
    "Europe/Belfast Europe/Berlin Europe/Bratislava Europe/Brussels Europe/Bucharest "
    "Europe/Budapest Europe/Busingen Europe/Copenhagen Europe/Dublin Europe/Gibraltar "
    "Europe/Guernsey Europe/Helsinki Europe/Isle_of_Man Europe/Jersey Europe/Lisbon "
    "Europe/Ljubljana Europe/London Europe/Luxembourg Europe/Madrid Europe/Malta Europe/Monaco "
    "Europe/Nicosia Europe/Oslo Europe/Paris Europe/Prague Europe/Riga Europe/Rome "
    "Europe/San_Marino Europe/Sofia Europe/Stockholm Europe/Tallinn Europe/Vaduz Europe/Vatican "
    "Europe/Vienna Europe/Vilnius Europe/Warsaw Europe/Zagreb Europe/Zurich "
).split())

_NO_ZONE = ("", "UTC", "UCT", "GMT", "Zulu", "Universal", "Greenwich", "Factory", "localtime")


def region_for_country(cc):
    """'na', 'eu' or None for an ISO country code ('CA', 'fr')."""
    cc = (cc or "").strip().upper()
    return "na" if cc in _NA_COUNTRIES else "eu" if cc in _EU_COUNTRIES else None


def region_for_timezone(tz):
    """'na', 'eu' or None for a tz name ('America/Toronto'). UTC and unknown names: None."""
    tz = (tz or "").strip().lstrip(":")
    if tz.startswith(("posix/", "right/")):
        tz = tz.split("/", 1)[1]
    if tz in _NO_ZONE or tz.startswith("Etc/"):
        return None
    return "na" if tz in _NA_ZONES else "eu" if tz in _EU_ZONES else None


def system_timezone(root="/"):
    """The system's tz name on Linux ('' when unset): $TZ, /etc/timezone, /etc/localtime."""
    tz = os.environ.get("TZ", "").strip().lstrip(":")
    if tz and not tz.startswith("/"):
        return tz
    try:
        with open(os.path.join(root, "etc/timezone"), encoding="utf-8") as f:
            tz = f.read().strip()
        if tz:
            return tz
    except OSError:
        pass
    try:
        path = os.path.realpath(os.path.join(root, "etc/localtime"))
        if "/zoneinfo/" in path:
            return path.split("/zoneinfo/", 1)[1]
    except OSError:
        pass
    return ""


def decide(country=None, timezone=None):
    """{"region": 'na'|'eu'|None, "frequency": Hz, "source": 'country'|'timezone'|'none',
    "from": the country code or tz name it was read from ('' when none)}.

    region None means nothing decided it: the frequency is then the 915 MHz fallback."""
    r = region_for_country(country)
    if r:
        return {"region": r, "frequency": FREQ[r], "source": "country", "from": country.strip().upper()}
    r = region_for_timezone(timezone)
    if r:
        return {"region": r, "frequency": FREQ[r], "source": "timezone", "from": timezone.strip()}
    return {"region": None, "frequency": FREQ[FALLBACK], "source": "none",
            "from": (timezone or "").strip()}


def describe(d):
    """One line for the radio screen: '915 MHz, from your time zone (America/Toronto)'."""
    mhz = f"{d['frequency'] / 1e6:g} MHz"
    if d.get("source") == "country":
        return f"{mhz}, from your country ({d['from']})"
    if d.get("source") == "timezone":
        return f"{mhz}, from your time zone ({d['from']})"
    if d.get("source") == "chosen":
        return f"{mhz}, chosen ({LABEL.get(d.get('region'), 'other')})"
    if d.get("source") == "kept":
        return "kept as it was set"
    where = f" ({d['from']})" if d.get("from") else ""
    return f"{mhz}: the time zone{where} doesn't say where you are. Check the local rules."
