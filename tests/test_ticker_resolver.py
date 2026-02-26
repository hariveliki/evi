"""Tests for ISIN -> ticker resolution."""

import pytest

import evi_weights.ticker_resolver as ticker_resolver


def test_extract_candidates_from_justetf_html():
    html = """
    <tr data-testid="etf-trade-data-panel_row-xlon">
      <td data-testid="etf-trade-data-panel_row-xlon_ticker">CSPX</td>
    </tr>
    <tr data-testid="etf-trade-data-panel_row-xetr">
      <td data-testid="etf-trade-data-panel_row-xetr_ticker">SXR8</td>
    </tr>
    <tr data-testid="etf-trade-data-panel_row-xpar">
      <td data-testid="etf-trade-data-panel_row-xpar_ticker">-</td>
    </tr>
    """
    got = ticker_resolver._extract_candidates_from_justetf_html(html)
    assert ("CSPX.L", "xlon") in got
    assert ("SXR8.DE", "xetr") in got
    assert ("SXR8", "xetr") not in got
    assert not any(symbol == "-" for symbol, _ in got)


def test_resolve_prefers_candidate_with_valuation(monkeypatch):
    monkeypatch.setattr(
        ticker_resolver,
        "_fetch_justetf_candidates",
        lambda isin: [("AAA.DE", "xetr"), ("BBB.L", "xlon")],
    )
    monkeypatch.setattr(ticker_resolver, "_search_yahoo_candidates", lambda isin: [])

    def fake_probe(symbol, listing):
        if symbol == "AAA.DE":
            return ticker_resolver.CandidateProbe(
                symbol=symbol,
                listing=listing,
                has_valuation=False,
                has_assets=True,
                name="No valuation",
                score=2,
            )
        return ticker_resolver.CandidateProbe(
            symbol=symbol,
            listing=listing,
            has_valuation=True,
            has_assets=True,
            name="Good candidate",
            score=7,
        )

    monkeypatch.setattr(ticker_resolver, "_probe_candidate", fake_probe)

    resolved = ticker_resolver.resolve_ticker_from_isin("IE00B5BMR087")
    assert resolved["ticker"] == "BBB.L"
    assert resolved["has_valuation"] is True


def test_rejects_invalid_isin():
    with pytest.raises(ValueError):
        ticker_resolver.resolve_ticker_from_isin("NOT-AN-ISIN")
