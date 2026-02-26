"""Resolve yfinance-compatible tickers from ETF ISINs."""

from __future__ import annotations

import re
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
_ROW_RE = re.compile(
    r'<tr[^>]*data-testid="etf-trade-data-panel_row-([a-z0-9]+)"[^>]*>(.*?)</tr>',
    re.IGNORECASE | re.DOTALL,
)
_TICKER_RE = re.compile(
    r'data-testid="etf-trade-data-panel_row-[^"]+_ticker"\s*>\s*([^<]+?)\s*</td>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")

# Maps justETF listing ids to Yahoo exchange suffixes.
_YAHOO_SUFFIX_BY_LISTING = {
    "xams": ".AS",  # Euronext Amsterdam
    "xber": ".BE",  # Berlin
    "xbru": ".BR",  # Euronext Brussels
    "xdus": ".DU",  # Dusseldorf
    "xfra": ".F",   # Frankfurt
    "xetr": ".DE",  # XETRA
    "xhel": ".HE",  # Helsinki
    "xlis": ".LS",  # Euronext Lisbon
    "xlon": ".L",   # London Stock Exchange
    "xmil": ".MI",  # Borsa Italiana
    "xmun": ".MU",  # Munich
    "xosl": ".OL",  # Oslo
    "xpar": ".PA",  # Euronext Paris
    "xsto": ".ST",  # Stockholm
    "xswx": ".SW",  # SIX Swiss Exchange
    "xvie": ".VI",  # Vienna
}

_LISTING_PREFERENCE = [
    "xlon",
    "xetr",
    "xpar",
    "xmil",
    "xams",
    "xswx",
    "xfra",
    "xdus",
    "xmun",
    "xber",
]
_LISTING_ORDER = {listing: idx for idx, listing in enumerate(_LISTING_PREFERENCE)}


@dataclass
class CandidateProbe:
    symbol: str
    listing: str | None
    has_valuation: bool
    has_assets: bool
    name: str | None
    score: int


def _normalize_isin(isin: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", isin).upper()
    if not _ISIN_RE.match(normalized):
        raise ValueError(f"Invalid ISIN: {isin}")
    return normalized


def _extract_candidates_from_justetf_html(html: str) -> list[tuple[str, str | None]]:
    candidates: list[tuple[str, str | None]] = []
    for listing, row_html in _ROW_RE.findall(html):
        ticker_match = _TICKER_RE.search(row_html)
        if not ticker_match:
            continue
        ticker_raw = _TAG_RE.sub("", ticker_match.group(1)).strip()
        if not ticker_raw or ticker_raw == "-":
            continue
        suffix = _YAHOO_SUFFIX_BY_LISTING.get(listing)
        if suffix:
            candidates.append((f"{ticker_raw}{suffix}".upper(), listing))
        else:
            candidates.append((ticker_raw.upper(), listing))
    return candidates


def _fetch_justetf_candidates(isin: str) -> list[tuple[str, str | None]]:
    url = f"https://www.justetf.com/en/etf-profile.html?isin={quote_plus(isin)}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    return _extract_candidates_from_justetf_html(html)


def _search_yahoo_candidates(isin: str) -> list[tuple[str, str | None]]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is required for ISIN ticker resolution.") from exc

    try:
        search = yf.Search(isin, max_results=20)
    except Exception:
        return []

    out: list[tuple[str, str | None]] = []
    for q in search.quotes or []:
        symbol = (q.get("symbol") or "").strip().upper()
        if symbol:
            out.append((symbol, None))
    return out


def _dedupe_candidates(candidates: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    seen: set[str] = set()
    unique: list[tuple[str, str | None]] = []
    for symbol, listing in candidates:
        if symbol in seen:
            continue
        seen.add(symbol)
        unique.append((symbol, listing))
    return unique


def _probe_candidate(symbol: str, listing: str | None) -> CandidateProbe:
    import yfinance as yf

    try:
        sink = StringIO()
        with redirect_stdout(sink), redirect_stderr(sink):
            info = yf.Ticker(symbol).info
    except Exception:
        info = {}

    pe = info.get("trailingPE") or info.get("forwardPE")
    pb = info.get("priceToBook")
    has_valuation = pe is not None or pb is not None
    has_assets = info.get("totalAssets") is not None or info.get("marketCap") is not None
    name = info.get("shortName") or info.get("longName")

    score = 0
    if has_valuation:
        score += 3
    if has_assets:
        score += 2
    if name:
        score += 1
    if listing is not None:
        score += max(0, 2 - _LISTING_ORDER.get(listing, 99))

    return CandidateProbe(
        symbol=symbol,
        listing=listing,
        has_valuation=has_valuation,
        has_assets=has_assets,
        name=name,
        score=score,
    )


def resolve_ticker_from_isin(isin: str) -> dict:
    """Resolve the most suitable yfinance ticker for an ISIN."""
    normalized_isin = _normalize_isin(isin)

    candidates = _fetch_justetf_candidates(normalized_isin)
    candidates.extend(_search_yahoo_candidates(normalized_isin))
    candidates = _dedupe_candidates(candidates)
    if not candidates:
        raise RuntimeError(f"No ticker candidates found for ISIN {normalized_isin}")

    probes = [_probe_candidate(symbol, listing) for symbol, listing in candidates]
    probes.sort(key=lambda p: (p.score, p.has_valuation, p.has_assets), reverse=True)
    best = probes[0]

    return {
        "isin": normalized_isin,
        "ticker": best.symbol,
        "has_valuation": best.has_valuation,
        "has_assets": best.has_assets,
        "name": best.name,
        "candidates_tested": [
            {
                "symbol": p.symbol,
                "listing": p.listing,
                "score": p.score,
                "has_valuation": p.has_valuation,
                "has_assets": p.has_assets,
                "name": p.name,
            }
            for p in probes
        ],
    }
