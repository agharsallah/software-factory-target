"""TED expert query builder for one CPV division and buyer countries."""

from collections.abc import Sequence
from datetime import date, datetime

# TED search API v3 fields needed to detect per-lot deadline changes (brief §3.3).
FIELDS: list[str] = [
    "publication-number",
    "notice-identifier",
    "notice-version",
    "procedure-identifier",
    "change-notice-version-identifier",
    "change-reason-code",
    "identifier-lot",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "deadline-receipt-request-date-lot",
    "buyer-country",
    "classification-cpv",
    "notice-type",
    "links",
]

# Change notices only: reason codes other than "none".
_CHANGE_REASON_CODES: tuple[str, ...] = (
    "update-add",
    "cor-buy",
    "cor-pub",
    "info-release",
    "susp-review",
    "cancel-intent",
)

# ISO 3166-1 alpha-2 / alpha-3 pairs. Officially assigned codes only.
_ISO_PAIRS = """
AD AND AE ARE AF AFG AG ATG AI AIA AL ALB AM ARM AO AGO AQ ATA AR ARG AS ASM
AT AUT AU AUS AW ABW AX ALA AZ AZE BA BIH BB BRB BD BGD BE BEL BF BFA BG BGR
BH BHR BI BDI BJ BEN BL BLM BM BMU BN BRN BO BOL BQ BES BR BRA BS BHS BT BTN
BV BVT BW BWA BY BLR BZ BLZ CA CAN CC CCK CD COD CF CAF CG COG CH CHE CI CIV
CK COK CL CHL CM CMR CN CHN CO COL CR CRI CU CUB CV CPV CW CUW CX CXR CY CYP
CZ CZE DE DEU DJ DJI DK DNK DM DMA DO DOM DZ DZA EC ECU EE EST EG EGY EH ESH
ER ERI ES ESP ET ETH FI FIN FJ FJI FK FLK FM FSM FO FRO FR FRA GA GAB GB GBR
GD GRD GE GEO GF GUF GG GGY GH GHA GI GIB GL GRL GM GMB GN GIN GP GLP GQ GNQ
GR GRC GS SGS GT GTM GU GUM GW GNB GY GUY HK HKG HM HMD HN HND HR HRV HT HTI
HU HUN ID IDN IE IRL IL ISR IM IMN IN IND IO IOT IQ IRQ IR IRN IS ISL IT ITA
JE JEY JM JAM JO JOR JP JPN KE KEN KG KGZ KH KHM KI KIR KM COM KN KNA KP PRK
KR KOR KW KWT KY CYM KZ KAZ LA LAO LB LBN LC LCA LI LIE LK LKA LR LBR LS LSO
LT LTU LU LUX LV LVA LY LBY MA MAR MC MCO MD MDA ME MNE MF MAF MG MDG MH MHL
MK MKD ML MLI MM MMR MN MNG MO MAC MP MNP MQ MTQ MR MRT MS MSR MT MLT MU MUS
MV MDV MW MWI MX MEX MY MYS MZ MOZ NA NAM NC NCL NE NER NF NFK NG NGA NI NIC
NL NLD NO NOR NP NPL NR NRU NU NIU NZ NZL OM OMN PA PAN PE PER PF PYF PG PNG
PH PHL PK PAK PL POL PM SPM PN PCN PR PRI PS PSE PT PRT PW PLW PY PRY QA QAT
RE REU RO ROU RS SRB RU RUS RW RWA SA SAU SB SLB SC SYC SD SDN SE SWE SG SGP
SH SHN SI SVN SJ SJM SK SVK SL SLE SM SMR SN SEN SO SOM SR SUR SS SSD ST STP
SV SLV SX SXM SY SYR SZ SWZ TC TCA TD TCD TF ATF TG TGO TH THA TJ TJK TK TKL
TL TLS TM TKM TN TUN TO TON TR TUR TT TTO TV TUV TW TWN TZ TZA UA UKR UG UGA
UM UMI US USA UY URY UZ UZB VA VAT VC VCT VE VEN VG VGB VI VIR VN VNM VU VUT
WF WLF WS WSM YE YEM YT MYT ZA ZAF ZM ZMB ZW ZWE
"""

_ISO_TOKENS = _ISO_PAIRS.split()
_ISO2_TO_ISO3 = dict(zip(_ISO_TOKENS[0::2], _ISO_TOKENS[1::2], strict=True))
_ISO_COUNTRIES = frozenset(_ISO2_TO_ISO3) | frozenset(_ISO2_TO_ISO3.values())


def _validate_division(cpv_division: object) -> str:
    """Return a 2-digit CPV division or raise ValueError."""
    if not isinstance(cpv_division, str):
        raise ValueError(f"cpv_division must be exactly 2 digits, got {cpv_division!r}")
    division = cpv_division.strip()
    if len(division) != 2 or not division.isdigit():
        raise ValueError(f"cpv_division must be exactly 2 digits, got {cpv_division!r}")
    return division


def _validate_countries(countries: object) -> list[str]:
    """Return uppercase ISO country codes or raise ValueError."""
    if isinstance(countries, str) or not isinstance(countries, Sequence) or len(countries) == 0:
        raise ValueError("countries must be a non-empty list of ISO country codes")
    normalized: list[str] = []
    for country in countries:
        if not isinstance(country, str):
            raise ValueError(f"non-ISO country: {country!r}")
        code = country.strip().upper()
        if code not in _ISO_COUNTRIES:
            raise ValueError(f"non-ISO country: {country!r}")
        normalized.append(code)
    return normalized


def _coerce_date(value: object) -> date:
    """Parse a date, datetime, ISO string, or YYYYMMDD string."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 8 and text.isdigit():
            try:
                return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            except ValueError as exc:
                raise ValueError(f"invalid date: {value!r}") from exc
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(text).date()
        except ValueError as exc:
            raise ValueError(f"invalid date: {value!r}") from exc
    raise ValueError(f"invalid date: {value!r}")


def build_query(
    cpv_division: str,
    countries: list[str],
    since: date | str,
    until: date | str,
) -> str:
    """Build a TED expert query for change notices in one CPV division.

    The query filters buyer countries, matches ``classification-cpv`` by
    division prefix, restricts ``publication-date`` to the inclusive window,
    and keeps change notices only (reason codes other than ``none``).

    ``cpv_division`` must be exactly two digits. Each country must be an
    ISO 3166-1 alpha-2 or alpha-3 code. Dates may be :class:`date` values
    or strings (``YYYY-MM-DD`` or ``YYYYMMDD``) and are rendered as
    ``YYYY-MM-DD``. Raises ValueError on invalid division or country.
    """
    division = _validate_division(cpv_division)
    codes = _validate_countries(countries)
    start = _coerce_date(since).isoformat()
    end = _coerce_date(until).isoformat()
    if len(codes) == 1:
        country_clause = f"buyer-country = {codes[0]}"
    else:
        country_clause = f"buyer-country IN ({' '.join(codes)})"
    reasons = " ".join(_CHANGE_REASON_CODES)
    return (
        f"{country_clause} "
        f"AND classification-cpv = {division}* "
        f"AND publication-date >= {start} "
        f"AND publication-date <= {end} "
        f"AND change-reason-code IN ({reasons})"
    )
