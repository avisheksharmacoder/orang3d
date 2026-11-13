"""
Common utilities for orang3D standalone simulation scripts.
Provides clean ASCII table formatting, benchmark assertion checking, and console banners.
"""

import os
from typing import Any, List, Optional, Tuple

# Ensure headless Qt operation if not set
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def print_banner(sim_num: int, title: str, benchmark_ref: str, governing_code: str) -> None:
    """Prints a standardized professional ASCII header banner."""
    width = 82
    print("=" * width)
    print(f" orang3D ENGINEERING SIMULATION {sim_num:02d}: {title.upper()}")
    print("-" * width)
    print(f" Benchmark Reference: {benchmark_ref}")
    print(f" Governing Standard:  {governing_code}")
    print("=" * width)


def print_section(heading: str) -> None:
    """Prints a section heading with divider line."""
    print(f"\n--- {heading.upper()} " + "-" * max(10, 75 - len(heading)))


def format_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> str:
    """Formats rows of data into a crisp ASCII table with column auto-sizing."""
    str_rows = [[str(cell) for cell in row] for row in rows]
    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for idx, cell in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(cell))
            else:
                col_widths.append(len(cell))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"

    lines = []
    if title:
        lines.append(f"[{title}]")
    lines.append(sep)
    lines.append(header_line)
    lines.append(sep)
    for row in str_rows:
        row_line = "| " + " | ".join(c.ljust(w) for c, w in zip(row, col_widths)) + " |"
        lines.append(row_line)
    lines.append(sep)
    return "\n".join(lines)


def check_benchmark(
    name: str,
    calculated: float,
    target: float,
    tolerance_pct: float = 0.50,
    unit: str = "",
) -> Tuple[bool, float, str]:
    """
    Computes relative percentage error against benchmark target.
    Returns (is_passed, relative_error_pct, formatted_message).
    """
    if abs(target) > 1e-12:
        rel_err = abs(calculated - target) / abs(target) * 100.0
    else:
        rel_err = abs(calculated - target) * 100.0

    passed = rel_err <= tolerance_pct
    status = "[PASS]" if passed else "[FAIL]"
    unit_str = f" {unit}" if unit else ""
    msg = (
        f"{name:<28} | Calc: {calculated:8.3f}{unit_str} | Target: {target:8.3f}{unit_str} "
        f"| Diff: {rel_err:5.2f}% (Limit: <={tolerance_pct:.2f}%) | {status}"
    )
    return passed, rel_err, msg

