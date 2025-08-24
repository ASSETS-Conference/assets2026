#!/usr/bin/env python3
"""
Generate the **Full Schedule** HTML sections from the ASSETS 2025 content CSV.

This version parses titles and authors directly from each `Paper N` cell and
adds stable anchor IDs to each time-slot so you can cross-link from elsewhere.

Anchor ID pattern (example):
  monday-paper-session-1a-inclusive-mixed-reality-0900-1045
  tuesday-coffee-break-1030-1100
If duplicates arise, a suffix -x2, -x3, ... is appended to ensure uniqueness.

Usage:
    python generate_full_schedule.py /path/to/content.csv > full_schedule.html
    python generate_full_schedule.py /path/to/content.csv -o full_schedule.html
"""
import sys, re, argparse
from pathlib import Path
from datetime import datetime
import math
import pandas as pd
import unicodedata

# ---------------------------- Utilities ----------------------------

WEEKDAY_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
}
MONTH_NAMES = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"
}

def safe_cell_str(row, colname: str) -> str:
    v = row.get(colname)
    if v is None:
        return ""
    # Catch pandas NA/NaN
    if pd.isna(v):
        return ""
    # Defensive: also handle plain float NaN
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()

def parse_date_label(date_str: str) -> str:
    """Turn '10/27/2025' into 'Monday, October 27, 2025'."""
    date_str = str(date_str).strip()
    dt = None
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m-%d-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            pass
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
    return slugify(str(date_str).strip())

def normalize_time_range(time_str: str) -> str:
    """Normalize '9:00AM-10:45AM' to '9:00 AM – 10:45 AM'; keep 'TBD' as-is."""
    if not isinstance(time_str, str):
        return ""
    t = time_str.strip()
    if t.upper() == "TBD":
        return "TBD"
    # ensure spaces before AM/PM
    t = re.sub(r"(?i)\s*(AM|PM)", r" \1", t)
    # normalize separators
    t = t.replace("-", " – ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def html_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def slugify(s: str) -> str:
    """
    ASCII slug: lowercase, strip accents, keep a–z0–9 and hyphens,
    collapse whitespace and punctuation to single hyphen.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s

def _parse_single_time_to_24h_token(t: str):
    """
    Parse a single time like '9', '9:00', '9:00 AM', '14:15' -> '0900', '1415'.
    Returns None if cannot parse.
    """
    if not isinstance(t, str):
        return None
    s = t.strip().lower()
    # capture am/pm if present
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?$", s)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2) or "00")
    ampm = (m.group(3) or "").replace(".", "")
    if ampm in ("am", "pm"):
        if hh == 12:
            hh = 0 if ampm == "am" else 12
        elif ampm == "pm":
            hh += 12
    # clamp minutes
    mm = max(0, min(mm, 59))
    return f"{hh:02d}{mm:02d}"

def time_range_token(time_str: str) -> str:
    """
    Convert a possibly messy time range into HHMM-HHMM token; 'TBD' -> 'tbd'.
    Accepts forms like:
      '9:00 AM – 10:45 AM', '09:00-10:45', '9-10:45am', 'TBD'
    """
    if not isinstance(time_str, str):
        return ""
    s = time_str.strip()
    if not s:
        return ""
    if s.upper() == "TBD":
        return "tbd"

    # try to split on en dash, em dash, or hyphen
    parts = re.split(r"\s*[–—-]\s*", s)
    if len(parts) != 2:
        # not a proper range, try parse as single time
        tok = _parse_single_time_to_24h_token(s)
        return tok or ""
    start_raw, end_raw = parts[0], parts[1]

    # If AM/PM is only on the end, copy it to start for parsing convenience
    ampm_end = re.search(r"(?i)\b([AP]\.?M\.?)\b", end_raw or "")
    if ampm_end and not re.search(r"(?i)\b([AP]\.?M\.?)\b", start_raw or ""):
        start_raw = f"{start_raw} {ampm_end.group(1)}"

    start_tok = _parse_single_time_to_24h_token(start_raw)
    end_tok = _parse_single_time_to_24h_token(end_raw)
    if start_tok and end_tok:
        return f"{start_tok}-{end_tok}"
    # fallback
    return slugify(s)

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

# ---------------------------- Slot ID generation ----------------------------

def make_slot_id(day_anchor: str, time_text: str, session_type: str, session_name: str, registry: set) -> str:
    """
    Build a stable, readable, unique anchor ID for a time-slot.
    Pattern: {day}-{session-type}-{session-name?}-{time-token}
    Examples:
      monday-paper-session-1a-inclusive-mixed-reality-0900-1045
      tuesday-coffee-break-1030-1100
      wednesday-keynote-opening-0900-1000
    Uniqueness is enforced within the day via -x2, -x3... suffix.
    """
    st_slug = slugify(session_type or "")
    sn_slug = slugify(session_name or "")
    # Use normalized "pretty" time (already formatted) to extract a compact token
    ttok = time_range_token(time_text or "")
    parts = [p for p in [day_anchor, st_slug, sn_slug or None, ttok or None] if p]
    base = "-".join(parts) if parts else day_anchor or "timeslot"
    anchor = base
    # Ensure uniqueness (within page: we track per-day in render_day_section)
    i = 2
    while anchor in registry:
        anchor = f"{base}-x{i}"
        i += 1
    registry.add(anchor)
    return anchor

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

def render_time_slot(row, day_anchor: str, id_registry: set):
    # Time text as shown in UI
    time_text = normalize_time_range(
        safe_cell_str(row, "Time (MT) ") or safe_cell_str(row, "Time (MT)")
    )
    session_type = safe_cell_str(row, "Session Type")
    session_name = safe_cell_str(row, "Session Name")
    slot_class = classify_slot(session_type)

    # Build a stable, unique anchor id for this slot
    slot_id = make_slot_id(day_anchor, time_text, session_type, session_name, id_registry)

    header = []
    header.append(f'            <div id="{slot_id}" class="{slot_class}">')
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

    # Track IDs within this day to prevent duplicates
    id_registry = set()

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
        html.append(render_time_slot(r, anchor, id_registry))

    html.append('          </section>')
    return "\n".join(html)

# ---------------------------- Main ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Generate Full Schedule HTML from content CSV (authors parsed in-cell) with stable anchor IDs per time-slot.")
    ap.add_argument("csv", help="Path to content.csv")
    ap.add_argument("-o","--output", help="Write HTML to this file (defaults to stdout)")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if "Time (MT) " not in df.columns and "Time (MT)" in df.columns:
        df["Time (MT) "] = df["Time (MT)"]
    if "Date" not in df.columns:
        raise ValueError("CSV is missing required column 'Date'")
    df["Date"] = df["Date"].ffill()

    # keep only rows that actually have a session
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
