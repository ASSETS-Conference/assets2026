#!/usr/bin/env python3
"""
Convert an accepted-papers CSV into copy-pasteable HTML blocks.

Expected CSV columns (case-sensitive):
- Type: e.g., "Technical Paper", "Experience Report", "TACCESS Article"
- Title: paper title (quotes are fine; will be HTML-escaped)
- Authors: semicolon-separated list, e.g. "First Last; Second Last; ..."

Usage:
    python converter.py input.csv > output.txt
    # or
    python generate_accepted_papers_html.py input.csv -o output.txt
"""
import argparse
import sys
import pandas as pd
from html import escape
from pathlib import Path

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

        author_list_items = "\n    ".join(f"<li>{a}</li>" for a in authors)
        block = f"""<div class="accepted-paper">
  <h2>{title_html}</h2>
  <p class="paper-type">{typ_html}</p>
  <ul class="author-list">
    {author_list_items}
  </ul>
</div>"""
        blocks.append(block)

    return "\n\n".join(blocks)

def main():
    parser = argparse.ArgumentParser(description="Convert accepted papers CSV to HTML blocks.")
    parser.add_argument("input_csv", help="Path to CSV with columns: Type, Title, Authors")
    parser.add_argument("-o", "--output", help="Write HTML to this file (otherwise prints to stdout)")
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)
    html = df_to_html_blocks(df)

    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)

if __name__ == "__main__":
    main()
