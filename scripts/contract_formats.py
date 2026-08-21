import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

import rfc3339_validator
from jsonschema import FormatChecker


_LEAP_SECOND = re.compile(r"(?<=T\d{2}:\d{2}:)60(?=(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$)")
_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")


def _normalize_rfc3339_datetime(value: str) -> str:
    normalized = value
    if len(normalized) > 10 and normalized[10] == "t":
        normalized = f"{normalized[:10]}T{normalized[11:]}"
    if normalized.endswith("z"):
        normalized = f"{normalized[:-1]}Z"
    return _LEAP_SECOND.sub("59", normalized, count=1)


def _is_dns_or_ipv4_hostname(hostname: str) -> bool:
    try:
        ipaddress.IPv4Address(hostname)
        return True
    except ValueError:
        pass

    if hostname == "localhost" or hostname.endswith(".") or len(hostname) > 253:
        return hostname == "localhost"
    if re.fullmatch(r"[0-9.]+", hostname):
        return False
    return all(_DNS_LABEL.fullmatch(label) for label in hostname.split("."))


def _is_bracketed_ipv6_netloc(netloc: str) -> bool:
    closing_bracket = netloc.find("]")
    if not netloc.startswith("[") or closing_bracket == -1:
        return False

    raw_host = netloc[1:closing_bracket]
    suffix = netloc[closing_bracket + 1 :]
    if suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()):
        return False

    try:
        ipaddress.IPv6Address(raw_host)
    except ValueError:
        return False
    return True


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time")
def is_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str) or "\r" in value or "\n" in value:
        return False
    return rfc3339_validator.validate_rfc3339(_normalize_rfc3339_datetime(value))


@FORMAT_CHECKER.checks("cumcm-http-url")
def is_cumcm_http_url(value: object) -> bool:
    if not isinstance(value, str) or any(
        character.isspace() or unicodedata.category(character) == "Cc" for character in value
    ):
        return False

    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return False

    if parts.scheme not in {"http", "https"} or not parts.netloc or "@" in parts.netloc:
        return False
    if port is not None and not 0 <= port <= 65535:
        return False

    hostname = parts.hostname
    if not hostname:
        return False
    if parts.netloc.startswith("["):
        return _is_bracketed_ipv6_netloc(parts.netloc)
    return _is_dns_or_ipv4_hostname(hostname)
