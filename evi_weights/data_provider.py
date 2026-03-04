"""Data providers for EVI calculation: sample data, JSON files, and live fetching."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

from evi_weights.config import EVIConfig, RegionConfig
from evi_weights.models import RegionData, ValuationSnapshot

_REGION_PROFILES = {
    "North America": {
        "pe_base": 18.0,
        "pe_trend": 0.3,
        "pe_cycle_amp": 3.5,
        "pe_covid_dip": -6.0,
        "pe_boom": 8.0,
        "pe_correction": -5.0,
        "pb_base": 2.8,
        "pb_trend": 0.08,
        "pb_cycle_amp": 0.5,
        "pb_covid_dip": -0.8,
        "pb_boom": 1.4,
        "pb_correction": -0.8,
        "mcap_base": 0.55,
        "mcap_trend": 0.006,
    },
    "Europe": {
        "pe_base": 15.5,
        "pe_trend": 0.1,
        "pe_cycle_amp": 2.0,
        "pe_covid_dip": -4.0,
        "pe_boom": 3.5,
        "pe_correction": -2.5,
        "pb_base": 1.75,
        "pb_trend": 0.02,
        "pb_cycle_amp": 0.25,
        "pb_covid_dip": -0.4,
        "pb_boom": 0.4,
        "pb_correction": -0.3,
        "mcap_base": 0.17,
        "mcap_trend": -0.002,
    },
    "Emerging Markets": {
        "pe_base": 13.0,
        "pe_trend": 0.0,
        "pe_cycle_amp": 2.5,
        "pe_covid_dip": -3.5,
        "pe_boom": 4.0,
        "pe_correction": -3.0,
        "pb_base": 1.55,
        "pb_trend": 0.01,
        "pb_cycle_amp": 0.2,
        "pb_covid_dip": -0.35,
        "pb_boom": 0.35,
        "pb_correction": -0.25,
        "mcap_base": 0.12,
        "mcap_trend": -0.001,
    },
    "Small Caps": {
        "pe_base": 20.0,
        "pe_trend": 0.15,
        "pe_cycle_amp": 3.0,
        "pe_covid_dip": -5.5,
        "pe_boom": 6.0,
        "pe_correction": -4.0,
        "pb_base": 1.9,
        "pb_trend": 0.03,
        "pb_cycle_amp": 0.3,
        "pb_covid_dip": -0.5,
        "pb_boom": 0.5,
        "pb_correction": -0.4,
        "mcap_base": 0.05,
        "mcap_trend": 0.0,
    },
    "Japan": {
        "pe_base": 15.0,
        "pe_trend": 0.1,
        "pe_cycle_amp": 2.0,
        "pe_covid_dip": -3.0,
        "pe_boom": 3.0,
        "pe_correction": -2.0,
        "pb_base": 1.25,
        "pb_trend": 0.015,
        "pb_cycle_amp": 0.15,
        "pb_covid_dip": -0.25,
        "pb_boom": 0.25,
        "pb_correction": -0.15,
        "mcap_base": 0.06,
        "mcap_trend": 0.0,
    },
    "Pacific ex-Japan": {
        "pe_base": 15.0,
        "pe_trend": 0.05,
        "pe_cycle_amp": 2.0,
        "pe_covid_dip": -3.5,
        "pe_boom": 3.0,
        "pe_correction": -2.5,
        "pb_base": 1.55,
        "pb_trend": 0.01,
        "pb_cycle_amp": 0.2,
        "pb_covid_dip": -0.3,
        "pb_boom": 0.3,
        "pb_correction": -0.2,
        "mcap_base": 0.025,
        "mcap_trend": 0.0,
    },
}

_QUARTER_END_MONTHS = [3, 6, 9, 12]


def _quarter_end_dates(start_year: int, end_year: int) -> list[date]:
    """Generate quarter-end dates from start_year Q1 through end_year Q4."""
    dates = []
    for year in range(start_year, end_year + 1):
        for month in _QUARTER_END_MONTHS:
            if month in (1, 3, 5, 7, 8, 10, 12):
                day = 31
            elif month in (4, 6, 9, 11):
                day = 30
            else:
                day = 28
            if month == 3:
                day = 31
            elif month == 6:
                day = 30
            elif month == 9:
                day = 30
            elif month == 12:
                day = 31
            dates.append(date(year, month, day))
    return dates


def _generate_series(
    n_quarters: int,
    base: float,
    trend_per_q: float,
    cycle_amp: float,
    covid_dip: float,
    boom: float,
    correction: float,
    rng: np.random.Generator,
    noise_scale: float = 0.02,
) -> list[float]:
    """Generate a realistic time series with trend, cycle, and event shocks."""
    values = []
    covid_q = 24  # Q1 2020 (quarter index from Q1 2014)
    boom_peak_q = 30  # Q3 2021
    correction_q = 33  # Q2 2022

    for i in range(n_quarters):
        trend = base + trend_per_q * i
        cycle = cycle_amp * math.sin(2 * math.pi * i / 16)

        shock = 0.0
        if i == covid_q:
            shock = covid_dip
        elif i == covid_q + 1:
            shock = covid_dip * 0.4
        elif covid_q + 2 <= i <= boom_peak_q:
            t = (i - covid_q - 2) / (boom_peak_q - covid_q - 2)
            shock = boom * t
        elif i == boom_peak_q:
            shock = boom
        elif boom_peak_q < i <= correction_q:
            t = (i - boom_peak_q) / (correction_q - boom_peak_q)
            shock = boom * (1 - t) + correction * t
        elif correction_q < i <= correction_q + 3:
            t = (i - correction_q) / 3
            shock = correction * (1 - t)

        noise = rng.normal(0, abs(base) * noise_scale)
        val = max(trend + cycle + shock + noise, base * 0.4)
        values.append(round(val, 2))

    return values


def generate_sample_data(
    config: EVIConfig,
    start_year: int = 2014,
    end_year: int = 2025,
) -> list[RegionData]:
    """Generate realistic sample historical data for all configured regions."""
    dates = _quarter_end_dates(start_year, end_year)
    n_quarters = len(dates)
    rng = np.random.default_rng(seed=42)

    region_data_list = []
    for region_cfg in config.regions:
        profile = _REGION_PROFILES.get(region_cfg.name)
        if profile is None:
            continue

        pe_series = _generate_series(
            n_quarters,
            profile["pe_base"],
            profile["pe_trend"],
            profile["pe_cycle_amp"],
            profile["pe_covid_dip"],
            profile["pe_boom"],
            profile["pe_correction"],
            rng,
            noise_scale=0.03,
        )
        pb_series = _generate_series(
            n_quarters,
            profile["pb_base"],
            profile["pb_trend"],
            profile["pb_cycle_amp"],
            profile["pb_covid_dip"],
            profile["pb_boom"],
            profile["pb_correction"],
            rng,
            noise_scale=0.02,
        )

        mcap_series = []
        for i in range(n_quarters):
            w = profile["mcap_base"] + profile["mcap_trend"] * i
            w += rng.normal(0, 0.005)
            mcap_series.append(round(max(w, 0.01), 4))

        history = []
        for i, d in enumerate(dates):
            history.append(
                ValuationSnapshot(
                    date=d,
                    pe_ratio=pe_series[i],
                    pb_ratio=pb_series[i],
                )
            )

        current = history[-1]

        region_data_list.append(
            RegionData(
                name=region_cfg.name,
                index_proxy=region_cfg.index_proxy,
                etf_ticker=region_cfg.etf_ticker,
                mcap_weight=mcap_series[-1],
                current=current,
                history=history,
            )
        )

    _normalize_mcap_weights(region_data_list)
    return region_data_list


def _normalize_mcap_weights(regions: list[RegionData]) -> None:
    """Normalize market cap weights to sum to 1.0."""
    total = sum(r.mcap_weight for r in regions)
    if total > 0:
        for r in regions:
            r.mcap_weight = round(r.mcap_weight / total, 6)


def load_data_from_json(path: str | Path, config: EVIConfig) -> list[RegionData]:
    """Load region data from a JSON file."""
    path = Path(path)
    with open(path) as f:
        raw = json.load(f)

    region_data_list = []
    for region_cfg in config.regions:
        rdata = raw.get("regions", {}).get(region_cfg.name)
        if rdata is None:
            continue

        history = []
        for entry in rdata.get("history", []):
            history.append(
                ValuationSnapshot(
                    date=date.fromisoformat(entry["date"]),
                    pe_ratio=entry.get("pe_ratio"),
                    pb_ratio=entry.get("pb_ratio"),
                    earnings_growth=entry.get("earnings_growth"),
                )
            )

        current_raw = rdata.get("current")
        if current_raw:
            current = ValuationSnapshot(
                date=date.fromisoformat(current_raw["date"]),
                pe_ratio=current_raw.get("pe_ratio"),
                pb_ratio=current_raw.get("pb_ratio"),
                earnings_growth=current_raw.get("earnings_growth"),
            )
        elif history:
            current = history[-1]
        else:
            continue

        region_data_list.append(
            RegionData(
                name=region_cfg.name,
                index_proxy=region_cfg.index_proxy,
                etf_ticker=region_cfg.etf_ticker,
                mcap_weight=rdata.get("mcap_weight", 0.0),
                current=current,
                history=history,
            )
        )

    return region_data_list


def export_data_to_json(regions: list[RegionData], path: str | Path) -> None:
    """Export region data to a JSON file for future use."""
    path = Path(path)
    output: dict = {"regions": {}}

    for r in regions:
        history_dicts = []
        for snap in r.history:
            entry: dict = {"date": snap.date.isoformat()}
            if snap.pe_ratio is not None:
                entry["pe_ratio"] = snap.pe_ratio
            if snap.pb_ratio is not None:
                entry["pb_ratio"] = snap.pb_ratio
            if snap.earnings_growth is not None:
                entry["earnings_growth"] = snap.earnings_growth
            history_dicts.append(entry)

        output["regions"][r.name] = {
            "index_proxy": r.index_proxy,
            "etf_ticker": r.etf_ticker,
            "mcap_weight": r.mcap_weight,
            "current": {
                "date": r.current.date.isoformat(),
                "pe_ratio": r.current.pe_ratio,
                "pb_ratio": r.current.pb_ratio,
            },
            "history": history_dicts,
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)


def fetch_live_data(config: EVIConfig) -> list[RegionData]:
    """Attempt to fetch live data via yfinance. Falls back to sample data on failure."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed, falling back to sample data.")
        return generate_sample_data(config)

    region_data_list = []
    for region_cfg in config.regions:
        try:
            ticker = yf.Ticker(region_cfg.etf_ticker)
            info = ticker.info

            pe = info.get("trailingPE") or info.get("forwardPE")
            pb = info.get("priceToBook")

            if pe is None and pb is None:
                raise ValueError(f"No valuation data for {region_cfg.etf_ticker}")

            mcap = info.get("totalAssets") or info.get("marketCap") or 0

            current = ValuationSnapshot(
                date=config.effective_date,
                pe_ratio=round(pe, 2) if pe else None,
                pb_ratio=round(pb, 2) if pb else None,
            )

            region_data_list.append(
                RegionData(
                    name=region_cfg.name,
                    index_proxy=region_cfg.index_proxy,
                    etf_ticker=region_cfg.etf_ticker,
                    mcap_weight=mcap,
                    current=current,
                    history=[current],
                )
            )
        except Exception as e:
            print(f"Warning: Failed to fetch data for {region_cfg.name}: {e}")
            continue

    if len(region_data_list) < len(config.regions):
        print("Incomplete live data, falling back to sample data.")
        return generate_sample_data(config)

    _normalize_mcap_weights(region_data_list)
    return region_data_list


def get_region_data(
    config: EVIConfig,
    source: str = "sample",
    json_path: Optional[str | Path] = None,
) -> list[RegionData]:
    """Main entry point for loading region data.

    Args:
        config: The EVI configuration.
        source: One of "sample", "json", or "live".
        json_path: Path to JSON file (required if source="json").
    """
    if source == "json":
        if json_path is None:
            raise ValueError("json_path required when source='json'")
        return load_data_from_json(json_path, config)
    elif source == "live":
        return fetch_live_data(config)
    else:
        return generate_sample_data(config)
