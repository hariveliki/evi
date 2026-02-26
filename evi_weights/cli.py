"""Command-line interface for the EVI Weights Calculator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tabulate import tabulate

from evi_weights.calculator import calculate_evi_weights
from evi_weights.config import load_config
from evi_weights.data_provider import (
    export_data_to_json,
    generate_sample_data,
    get_region_data,
)
from evi_weights.ticker_resolver import resolve_ticker_from_isin


def _format_pct(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def _format_float(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


def _format_score(val: float | None, decimals: int = 4) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.{decimals}f}"


def print_results(result, verbose: bool = False) -> None:
    """Print EVI calculation results as a formatted table."""
    print(f"\n{'=' * 72}")
    print(f"  Equal-Value-Index (EVI) Weight Calculation")
    print(f"  As-of Date:      {result.as_of_date}")
    print(f"  Effective Date:  {result.effective_date}")
    print(f"{'=' * 72}\n")

    if not result.region_scores:
        print("  No regions to display.")
        return

    if verbose:
        _print_detailed(result)
    else:
        _print_summary(result)

    print(f"\n  Total EVI Weight: {_format_pct(result.total_weight)}")
    print()


def _print_summary(result) -> None:
    """Print compact summary table."""
    headers = ["Region", "MCAP Wt", "EVI Wt", "Delta (pp)", "Composite", "Adj Factor"]
    rows = []
    for rs in result.region_scores:
        delta_pp = (rs.final_weight - rs.mcap_weight) * 100
        direction = "+" if delta_pp > 0 else ""
        rows.append([
            rs.name,
            _format_pct(rs.mcap_weight),
            _format_pct(rs.final_weight),
            f"{direction}{delta_pp:.2f}pp",
            _format_score(rs.composite_score),
            _format_float(rs.adjustment_factor, 4),
        ])

    print(tabulate(rows, headers=headers, tablefmt="simple", stralign="right"))


def _print_detailed(result) -> None:
    """Print detailed diagnostic table."""
    headers = [
        "Region",
        "MCAP Wt",
        "Cur P/E",
        "Base P/E",
        "P/E Score",
        "Cur P/B",
        "Base P/B",
        "P/B Score",
        "Composite",
        "Adj Fac",
        "EVI Wt",
        "Delta",
    ]
    rows = []
    for rs in result.region_scores:
        delta_pp = (rs.final_weight - rs.mcap_weight) * 100
        direction = "+" if delta_pp > 0 else ""
        rows.append([
            rs.name,
            _format_pct(rs.mcap_weight),
            _format_float(rs.current_pe),
            _format_float(rs.baseline_pe),
            _format_score(rs.pe_score),
            _format_float(rs.current_pb),
            _format_float(rs.baseline_pb),
            _format_score(rs.pb_score),
            _format_score(rs.composite_score),
            _format_float(rs.adjustment_factor, 4),
            _format_pct(rs.final_weight),
            f"{direction}{delta_pp:.2f}pp",
        ])

    print(tabulate(rows, headers=headers, tablefmt="simple", stralign="right"))

    print(f"\n{'─' * 72}")
    print("  Interpretation:")
    print("    Composite > 0 → overvalued vs history → EVI reduces weight")
    print("    Composite < 0 → undervalued vs history → EVI increases weight")
    print("    Adj Factor > 1 → weight increase, < 1 → weight decrease")


def print_json_output(result) -> None:
    """Print results as JSON."""
    output = {
        "as_of_date": result.as_of_date.isoformat(),
        "effective_date": result.effective_date.isoformat(),
        "total_weight": round(result.total_weight, 6),
        "regions": result.to_dict(),
    }
    for r in output["regions"]:
        for key, val in r.items():
            if isinstance(val, float):
                r[key] = round(val, 6)
    print(json.dumps(output, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Calculate Equal-Value-Index (EVI) weights for world regions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python main.py                           # Run with sample data and defaults
  python main.py --verbose                 # Show detailed diagnostics
  python main.py --config my_config.yaml   # Use custom config
  python main.py --source live             # Fetch live data via yfinance
  python main.py --resolve-isin IE00B5BMR087
  python main.py --output json             # Output as JSON
  python main.py --export-data data.json   # Export sample data to JSON file
        """,
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--source",
        choices=["sample", "json", "live"],
        default="sample",
        help="Data source: sample (built-in), json (file), or live (yfinance)",
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default=None,
        help="Path to JSON data file (required if --source=json)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed diagnostic output",
    )
    parser.add_argument(
        "--output",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--export-data",
        type=str,
        default=None,
        help="Export generated sample data to a JSON file",
    )
    parser.add_argument(
        "--resolve-isin",
        type=str,
        default=None,
        help="Resolve an ETF ISIN to the best yfinance ticker and exit",
    )

    args = parser.parse_args(argv)

    if args.resolve_isin:
        try:
            resolved = resolve_ticker_from_isin(args.resolve_isin)
        except Exception as exc:
            print(f"Failed to resolve ticker from ISIN: {exc}", file=sys.stderr)
            sys.exit(1)

        if args.output == "json":
            print(json.dumps(resolved, indent=2))
        elif args.verbose:
            print(f"ISIN: {resolved['isin']}")
            print(f"Best ticker: {resolved['ticker']}")
            print(f"Has valuation data: {resolved['has_valuation']}")
            print(f"Has asset size data: {resolved['has_assets']}")
            if resolved["name"]:
                print(f"Name: {resolved['name']}")
            print("\nCandidates tested:")
            for item in resolved["candidates_tested"]:
                print(
                    f"  - {item['symbol']}"
                    f" (score={item['score']}, valuation={item['has_valuation']}, assets={item['has_assets']})"
                )
        else:
            print(resolved["ticker"])
        return

    config = load_config(args.config)

    region_data = get_region_data(
        config,
        source=args.source,
        json_path=args.data_file,
    )

    if args.export_data:
        export_data_to_json(region_data, args.export_data)
        print(f"Data exported to {args.export_data}")
        if args.output == "table":
            return

    result = calculate_evi_weights(config, region_data)

    if args.output == "json":
        print_json_output(result)
    else:
        print_results(result, verbose=args.verbose)
