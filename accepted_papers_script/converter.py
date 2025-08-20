#!/usr/bin/env python3
"""
Convert an accepted-papers CSV into two copy-pasteable HTML block files.

Expected CSV columns (case-sensitive):
- Type: e.g., "Technical Paper", "Experience Report", "TACCESS Article"
- Title: paper title (quotes are fine; will be HTML-escaped)
- Authors: semicolon-separated list, e.g. "First Last; Second Last; ..."

Usage:
    python generate_accepted_papers_html.py input.csv
    # or specify outputs explicitly:
    python generate_accepted_papers_html.py input.csv \
        --exp-output experience_reports.html \
        --other-output everything_else.html
"""
import argparse
import sys
import re
import pandas as pd
from html import escape
from pathlib import Path


def normalize_title_key(title: str) -> str:
    """
    Produce a sort key by stripping any leading non-alphabetic characters
    (quotes, punctuation, digits, whitespace, etc.) and lowercasing.
    """
    if title is None:
        return ""
    # Remove leading non-letters (A-Z or a-z)
    stripped = re.sub(r'^[^A-Za-z]+', '', str(title).strip())
    return stripped.lower()


def df_to_html_blocks(df: pd.DataFrame) -> str:
    # Validate columns
    for col in ("Type", "Title", "Authors"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    blocks = []
    for _, row in df.iterrows():
        typ = str(row["Type"]).strip()
        title = str(row["Title"]).strip()
        authors_raw = str(row["Authors"]).strip()

        typ_html = escape(typ)
        title_html = escape(title)

        # Split authors by semicolon (keeps commas inside names)
        authors = [escape(a.strip()) for a in authors_raw.split(";") if a.strip()]

        author_list_items = "\n".join(f"<li>{a}</li>" for a in authors)
        block = f"""<div class="accepted-paper">
  <h2>{title_html}</h2>
  <p class="paper-type">{typ_html}</p>
  <ul class="author-list">
    {author_list_items}
  </ul>
</div>"""
        blocks.append(block)

    return "\n\n".join(blocks)


def sort_df_for_output(df: pd.DataFrame) -> pd.DataFrame:
    # Create a stable sort: primary by normalized key, secondary by raw title
    df = df.copy()
    df["_sortkey"] = df["Title"].apply(normalize_title_key)
    df = df.sort_values(by=["_sortkey", "Title"], kind="mergesort").drop(columns=["_sortkey"])
    return df


def main():
    parser = argparse.ArgumentParser(description="Convert accepted papers CSV into two HTML block files: Experience Reports and Others.")
    parser.add_argument("input_csv", help="Path to CSV with columns: Type, Title, Authors")
    parser.add_argument("--exp-output", help="Write Experience Reports HTML to this file")
    parser.add_argument("--other-output", help="Write all non-Experience-Report HTML to this file")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        sys.exit(f"Input CSV not found: {input_path}")

    # Defaults if outputs not provided
    default_exp = input_path.with_name(f"{input_path.stem}_experience_reports.html")
    default_other = input_path.with_name(f"{input_path.stem}_others.html")

    exp_out = Path(args.exp_output) if args.exp_output else default_exp
    other_out = Path(args.other_output) if args.other_output else default_other

    df = pd.read_csv(input_path)

    # Identify Experience Reports (case-insensitive, tolerant of trailing text)
    type_series = df["Type"].astype(str).str.strip().str.lower()
    is_exp = type_series.str.startswith("experience report")

    df_exp = sort_df_for_output(df[is_exp])
    df_other = sort_df_for_output(df[~is_exp])

    html_exp = df_to_html_blocks(df_exp)
    html_other = df_to_html_blocks(df_other)

    exp_out.write_text(html_exp, encoding="utf-8")
    other_out.write_text(html_other, encoding="utf-8")

    # Brief status to stdout so you know where the files went
    sys.stdout.write(f"Wrote Experience Reports to: {exp_out}\n")
    sys.stdout.write(f"Wrote Others to: {other_out}\n")


if __name__ == "__main__":
    main()
