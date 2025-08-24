#!/usr/bin/env python3
"""
Generate the **Full Schedule** HTML sections from the ASSETS 2025 content CSV.

This version parses titles and authors directly from each `Paper N` cell.
Expected format inside a Paper cell:

    (TACCESS) Paper Title
    Author One; Author Two; Author Three

- First non-empty line = title (may start with a tag in parentheses).
- Remaining non-empty lines are joined and split on ';' into authors.
- If no authors are present, the paper renders without an author list.

Usage:
    python generate_full_schedule.py /path/to/content.csv > full_schedule.html
    python generate_full_schedule.py /path/to/content.csv -o full_schedule.html
"""
import sys, re, argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

# ---------------------------- Utilities ----------------------------

WEEKDAY_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
}
MONTH_NAMES = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"
}

def parse_date_label(date_str: str) -> str:
    """Turn '10/27/2025' into 'Monday, October 27, 2025'."""
    date_str = str(date_str).strip()
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m-%d-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            dt = None
    if dt is None:
        return date_str
    weekday = WEEKDAY_NAMES[dt.weekday()]
    month = MONTH_NAMES[dt.month]
    return f"{weekday}, {month} {dt.day}, {dt.year}"

def date_anchor_id(date_str: str) -> str:
    """Map a date to an anchor id used in your HTML ('monday', 'tuesday', ...)."""
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m-%d-%Y"):
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            return WEEKDAY_NAMES[dt.weekday()].lower()
        except ValueError:
            continue
    return re.sub(r"[^a-z0-9]+", "-", str(date_str).strip().lower()).strip("-")

def normalize_time_range(time_str: str) -> str:
    """Normalize '9:00AM-10:45AM' to '9:00 AM – 10:45 AM'; keep 'TBD' as-is."""
    if not isinstance(time_str, str):
        return ""
    t = time_str.strip()
    if t.upper() == "TBD":
        return "TBD"
    t = re.sub(r"(?i)\s*(AM|PM)", r" \1", t)
    t = t.replace("-", " – ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def classify_slot(session_type: str) -> str:
    """Return a CSS class for the time-slot based on the Session Type string."""
    if not isinstance(session_type, str):
        return "time-slot"
    st = session_type.strip().lower()
    if st.startswith("paper session"):
        return "time-slot paper-sessions"
    if "keynote" in st or "conference open" in st:
        return "time-slot keynote-slot"
    if "lunch" in st:
        return "time-slot lunch-slot"
    if "coffee" in st or "poster session" in st:
        return "time-slot break-slot"
    if "registration" in st:
        return "time-slot registration-slot"
    if ("student research competition" in st or "sigaccess business meeting" in st or
        "doctoral consortium" in st or "workshops" in st):
        return "time-slot special-slot"
    if "closing" in st:
        return "time-slot closing-slot"
    return "time-slot"

def html_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def extract_paper_tag_and_title(raw_title: str):
    """
    Titles may begin with a tag in parentheses:
      (TACCESS) ... / (ER) ... / (Short Paper) ... / (Honorable Mention) ...
    Returns (tag_class, tag_label, clean_title).
    """
    tag_class, tag_label = None, None
    title = (raw_title or "").strip()
    m = re.match(r"^\(([^)]+)\)\s*(.*)$", title)
    if m:
        token = m.group(1).strip().lower()
        rest = m.group(2).strip()
        mapping = {
            "taccess": ("taccess-tag", "TACCESS Paper"),
            "er": ("er-tag", "Experience Report"),
            "experience report": ("er-tag", "Experience Report"),
            "short": ("short-tag", "Short Paper"),
            "short paper": ("short-tag", "Short Paper"),
            "honorable mention": ("honorable-tag", "Honorable Mention"),
        }
        if token in mapping:
            tag_class, tag_label = mapping[token]
            title = rest
        else:
            title = rest
    return tag_class, tag_label, title

def parse_paper_cell(cell_text: str):
    """
    Parse a Paper cell into (title, authors_list).
    - First non-empty line is title (may include tag).
    - Remaining lines (or part after a separator) are authors.
    """
    if not isinstance(cell_text, str):
        return "", []
    lines = [ln.strip() for ln in cell_text.splitlines() if ln.strip()]
    if not lines:
        return "", []
    title_line = lines[0]
    authors_blob = " ".join(lines[1:]).strip()
    if not authors_blob and (" — " in title_line or " -- " in title_line or " | " in title_line):
        for sep in [" — ", " -- ", " | "]:
            if sep in title_line:
                title_line, authors_blob = [part.strip() for part in title_line.split(sep, 1)]
                break
    authors = [a.strip() for a in authors_blob.split(";") if a.strip()] if authors_blob else []
    return title_line, authors

# ---------------------------- Rendering ----------------------------

def render_paper_item_from_cell(cell_text: str):
    title_raw, authors_list = parse_paper_cell(cell_text)
    tag_class, tag_label, clean_title = extract_paper_tag_and_title(title_raw)
    parts = []
    parts.append('                  <div class="paper-item">')
    if tag_class and tag_label:
        parts.append('                    <div class="paper-tags">')
        parts.append(f'                      <span class="paper-tag {tag_class}">{html_escape(tag_label)}</span>')
        parts.append('                    </div>')
    parts.append(f'                    <h6 class="paper-title">{html_escape(clean_title)}</h6>')
    if authors_list:
        parts.append('                    <ul class="author-list">')
        for a in authors_list:
            parts.append(f'                      <li>{html_escape(a)}</li>')
        parts.append('                    </ul>')
    parts.append('                  </div>')
    return "\n".join(parts)

def render_paper_list(row):
    papers = []
    for i in range(1, 50):  # future-proof upper bound
        col = f"Paper {i}"
        if col in row and isinstance(row[col], str) and row[col].strip():
            papers.append(render_paper_item_from_cell(row[col]))
    return "\n".join(papers)

def render_time_slot(row):
    time_text = normalize_time_range(str(row.get("Time (MT) ", "") or row.get("Time (MT)", "")))
    session_type = str(row.get("Session Type") or "").strip()
    session_name = str(row.get("Session Name") or "").strip()
    slot_class = classify_slot(session_type)

    header = []
    header.append(f'            <div class="{slot_class}">')
    header.append('              <div class="time-slot-header">')
    header.append(f'                <span class="time-range">{html_escape(time_text or "TBD")}</span>')
    if session_type.lower().startswith("paper session"):
        header.append('                <h4 class="slot-title">')
        header.append(f'                  <span class="session-number">{html_escape(session_type)}</span>')
        header.append(f'                  <span class="session-topic">{html_escape(session_name)}</span>')
        header.append('                </h4>')
    else:
        header.append(f'                <h4 class="slot-title">{html_escape(session_type)}</h4>')
    header.append('              </div>')

    block = ""
    if session_type.lower().startswith("paper session"):
        paper_html = render_paper_list(row)
        if paper_html:
            block = "\n".join([
                "              ",
                '              <div class="program-block">',
                '                <div class="paper-list">',
                paper_html,
                '                </div>',
                '              </div>'
            ])

    footer = ["            </div>"]
    return "\n".join(header + ([block] if block else []) + footer)

def render_day_section(date_str: str, rows_for_day: pd.DataFrame, prev_anchor: str, next_anchor: str) -> str:
    label = parse_date_label(date_str)
    anchor = date_anchor_id(date_str)
    html = []
    html.append(f'          <!-- {label} -->')
    html.append(f'          <section class="day-schedule" id="{anchor}">')
    html.append('            <div class="day-header-container">')
    html.append(f'              <h3 class="day-header">{label}</h3>')
    html.append('              <div class="day-navigation">')
    if prev_anchor:
        html.append(f'                <a href="#{prev_anchor}" class="day-nav-btn day-nav-prev" title="Previous day">‹</a>')
    else:
        html.append('                <a href="#" class="day-nav-btn day-nav-prev day-nav-disabled" title="Previous day">‹</a>')
    if next_anchor:
        html.append(f'                <a href="#{next_anchor}" class="day-nav-btn day-nav-next" title="Next day">›</a>')
    else:
        html.append('                <a href="#" class="day-nav-btn day-nav-next day-nav-disabled" title="Next day">›</a>')
    html.append('              </div>')
    html.append('            </div>')

    for _, r in rows_for_day.iterrows():
        html.append(render_time_slot(r))

    html.append('          </section>')
    return "\n".join(html)

# ---------------------------- Main ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Generate Full Schedule HTML from content CSV (authors parsed in-cell).")
    ap.add_argument("csv", help="Path to content.csv")
    ap.add_argument("-o","--output", help="Write HTML to this file (defaults to stdout)")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if "Time (MT) " not in df.columns and "Time (MT)" in df.columns:
        df["Time (MT) "] = df["Time (MT)"]
    if "Date" not in df.columns:
        raise ValueError("CSV is missing required column 'Date'")
    df["Date"] = df["Date"].ffill()

    df = df[df["Session Type"].notna() & (df["Session Type"].astype(str).str.strip() != "")].copy()
    days = [(date, sub) for date, sub in df.groupby("Date", sort=False)]
    anchors = [date_anchor_id(d) for d,_ in days]

    out_lines = []
    for i, (date, sub) in enumerate(days):
        prev_a = anchors[i-1] if i > 0 else None
        next_a = anchors[i+1] if i+1 < len(anchors) else None
        out_lines.append(render_day_section(date, sub, prev_a, next_a))

    html = "\n\n".join(out_lines)
    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)

if __name__ == "__main__":
    main()
