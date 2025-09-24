#!/usr/bin/env python3
"""
Generate the **Full Schedule** HTML sections from the ASSETS 2025 content CSV.

Poster Sessions are externalized:
- First --poster-csv -> poster_sessions_a.txt (Session A)
- Second -> poster_sessions_b.txt (Session B)
- Third -> poster_sessions_c.txt (Session C)

The full schedule does NOT inline posters; it inserts an HTML comment
indicating which external file contains the Poster Session content.

Usage:
    python3 generate_full_schedule.py content.csv \
    --poster-csv monday=posters_monday.csv \
    --poster-csv tuesday=posters_tuesday.csv \
    --poster-csv wednesday=posters_wednesday.csv \
    -o full_output.txt
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

WEEKDAY_ABBR = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# --- NEW: posters export helpers ---

def render_posters_groups_only(df_posters: pd.DataFrame) -> str:
    """
    Return ONLY the <div class="poster-group">...</div> blocks (no outer container),
    grouped as Posters / SRC / Demos / DC (same grouping as render_posters_block).
    """
    if df_posters is None or df_posters.empty:
        return ""
    df = df_posters.copy()
    df["__Type"] = df["Presentation Type"].map(normalize_type_label)

    # preserve first-seen order, but prefer canonical sequence
    seen = []
    for t in df["__Type"]:
        if t not in seen:
            seen.append(t)
    preferred_order = ["Posters", "Student Research Competition", "Demos", "Doctoral Consortium"]
    preferred = [lbl for lbl in preferred_order if lbl in seen]
    others = [lbl for lbl in seen if lbl not in preferred]
    ordered_types = preferred + others

    groups_html = []
    for t in ordered_types:
        sub = df[df["__Type"] == t]
        if sub.empty:
            continue
        items = []
        for _, r in sub.iterrows():
            items.append(render_poster_item(r.get("Title",""), r.get("Authors","")))
        group_html = [
            '          <div class="poster-group">',
            f'            <h5 class="poster-group-title">{html_escape(t)}</h5>',
            '            <div class="paper-list">',
            "\n".join(items),
            '            </div>',
            '          </div>'
        ]
        groups_html.append("\n".join(group_html))

    return "\n".join(groups_html)


def render_posters_document(df_posters: pd.DataFrame, letter_label: str) -> str:
    """
    Wrap the poster groups with the exact comment framing you requested.
    """
    groups = render_posters_groups_only(df_posters)
    if not groups:
        return (
            f'          <!-- Start of Poster Session {letter_label} -->\n'
            f'          <!-- (No posters) -->\n'
            f'        <!--End of Poster Session {letter_label}-->'
        )
    return (
        f'          <!-- Start of Poster Session {letter_label} -->\n'
        f'{groups}\n'
        f'        <!--End of Poster Session {letter_label}-->'
    )


def safe_cell_str(row, colname: str) -> str:
    v = row.get(colname)
    if v is None:
        return ""
    if pd.isna(v):
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()

def _parse_date_any(date_str: str):
    s = str(date_str).strip()
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None

def parse_date_label_short(date_str: str) -> str:
    dt = _parse_date_any(date_str)
    if not dt:
        return str(date_str).strip()
    wd = WEEKDAY_ABBR[dt.weekday()]
    mo = MONTH_ABBR[dt.month - 1]
    yr2 = dt.year % 100
    return f"{wd} {mo} {dt.day} \u2019{yr2:02d}"

def date_iso_attr(date_str: str) -> str:
    dt = _parse_date_any(date_str)
    if not dt:
        return str(date_str).strip()
    return dt.strftime("%Y-%m-%d")

def parse_date_label(date_str: str) -> str:
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
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m-%d-%Y"):
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            return WEEKDAY_NAMES[dt.weekday()].lower()
        except ValueError:
            continue
    return slugify(str(date_str).strip())

def normalize_time_range(time_str: str) -> str:
    if not isinstance(time_str, str):
        return ""
    t = time_str.strip()
    if t.upper() == "TBD":
        return "TBD"
    t = re.sub(r"(?i)\s*(AM|PM)", r" \1", t)
    t = t.replace("-", " – ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def html_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def slugify(s: str) -> str:
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
    if not isinstance(t, str):
        return None
    s = t.strip().lower()
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
    mm = max(0, min(mm, 59))
    return f"{hh:02d}{mm:02d}"

def time_range_token(time_str: str) -> str:
    if not isinstance(time_str, str):
        return ""
    s = time_str.strip()
    if not s:
        return ""
    if s.upper() == "TBD":
        return "tbd"
    parts = re.split(r"\s*[–—-]\s*", s)
    if len(parts) != 2:
        tok = _parse_single_time_to_24h_token(s)
        return tok or ""
    start_raw, end_raw = parts[0], parts[1]
    ampm_end = re.search(r"(?i)\b([AP]\.?M\.?)\b", end_raw or "")
    if ampm_end and not re.search(r"(?i)\b([AP]\.?M\.?)\b", start_raw or ""):
        start_raw = f"{start_raw} {ampm_end.group(1)}"
    start_tok = _parse_single_time_to_24h_token(start_raw)
    end_tok = _parse_single_time_to_24h_token(end_raw)
    if start_tok and end_tok:
        return f"{start_tok}-{end_tok}"
    return slugify(s)

def classify_slot(session_type: str) -> str:
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
    authors = [a.strip() for a in re.split(r";", authors_blob) if a.strip()] if authors_blob else []
    return title_line, authors

# ---------------------------- Posters ingestion ----------------------------

POSTER_TYPE_ORDER = ["posters", "demos", "doctoral consortium"]

def _norm_col(df, targets):
    """Find first matching column (case/space-insensitive); return its name or None."""
    norm = {re.sub(r"\s+", "", c.strip().lower()): c for c in df.columns}
    for t in targets:
        key = re.sub(r"\s+", "", t.strip().lower())
        if key in norm:
            return norm[key]
    return None

def _split_authors(auth_blob: str):
    if not isinstance(auth_blob, str) or not auth_blob.strip():
        return []
    s = auth_blob.strip()
    if ";" in s:
        parts = [p.strip() for p in s.split(";")]
    else:
        # Split on commas not inside (...)
        parts = [p.strip() for p in re.split(r",(?![^()]*\))", s)]
    return [p for p in parts if p]


def load_posters_csv(path: str) -> pd.DataFrame:
    """
    Load a poster CSV and return a tidy DF with columns:
      Presentation Type (forward-filled), Title, Authors
    Accepts flexible column headers.
    """
    df = pd.read_csv(path)
    # Flexible headers
    type_col = _norm_col(df, ["Presentation Type", "Type", "Category"])
    title_col = _norm_col(df, ["Title", "Paper Title", "Work Title", "Demo Title"])
    authors_col = _norm_col(df, ["Authors", "Author(s)", "Author List"])

    if not title_col:
        raise ValueError(f"{path}: could not find a Title column")
    if not type_col:
        # If type is truly absent, assume all are Posters
        df["Presentation Type"] = "Posters"
        type_col = "Presentation Type"
    # Forward-fill type (only first row in block has it)
    df[type_col] = df[type_col].ffill()

    # Normalize & trim
    out = pd.DataFrame({
        "Presentation Type": df[type_col].astype(str).str.strip(),
        "Title": df[title_col].astype(str).str.strip(),
        "Authors": df[authors_col].astype(str).fillna("").str.strip() if authors_col else ""
    })
    # Drop empty titles
    out = out[out["Title"].astype(str).str.strip() != ""].copy()
    return out

def normalize_type_label(t: str) -> str:
    """Canonical labels for grouping/order."""
    key = (t or "").strip().lower()
    if key.startswith("poster"):
        return "Posters"
    if key.startswith("demo"):
        return "Demos"
    if key == "src" or "student research competition" in key:
        return "Student Research Competition"
    if key == "dc" or key.startswith("doctoral"):
        return "Doctoral Consortium"
    return t.strip().title() if t else "Posters"


# Robustly capture "(...)" at end, including nested parentheses
AFFIL_RE = re.compile(r"^(?P<name>.*?)\s*\((?P<aff>.*)\)\s*$")

def render_author_li(author_text: str) -> str:
    a = (author_text or "").strip()
    if not a:
        return ""
    m = AFFIL_RE.match(a)
    if m:
        name = html_escape(m.group("name").strip().strip(",;"))
        aff  = html_escape((m.group("aff") or "").strip())
        if aff:
            # NOTE: space is inside the affiliation span
            return f'                      <li>{name}<span class="affiliation"> {aff}</span></li>'
        # If empty parens somehow, fall through to plain name
        a = name
    return f'                      <li>{html_escape(a)}</li>'


def render_poster_item(title: str, authors_blob: str) -> str:
    authors = _split_authors(authors_blob)
    parts = []
    parts.append('                  <div class="paper-item">')
    parts.append('                    <h6 class="paper-title">')
    parts.append(f'                      {html_escape(title)}')
    parts.append('                    </h6>')
    if authors:
        parts.append('                    <!-- prettier-ignore -->')
        parts.append('                    <ul class="author-list">')
        for a in authors:
            parts.append(render_author_li(a))
        parts.append('                    </ul>')
    parts.append('                  </div>')
    return "\n".join(parts)

def render_posters_block(df_posters: pd.DataFrame) -> str:
    """
    Render grouped Posters/SRC/Demos/DC inside a <div class="program-block posters-block">.
    (Kept for reference; not used when externalizing posters.)
    """
    if df_posters is None or df_posters.empty:
        return ""
    df = df_posters.copy()
    df["__Type"] = df["Presentation Type"].map(normalize_type_label)

    # Preserve first-seen order but prefer canonical sequence
    seen = []
    for t in df["__Type"]:
        if t not in seen:
            seen.append(t)
    preferred_order = ["Posters", "Student Research Competition", "Demos", "Doctoral Consortium"]
    preferred = [lbl for lbl in preferred_order if lbl in seen]
    others = [lbl for lbl in seen if lbl not in preferred]
    ordered_types = preferred + others

    groups_html = []
    for t in ordered_types:
        sub = df[df["__Type"] == t]
        if sub.empty:
            continue
        items = []
        for _, r in sub.iterrows():
            items.append(render_poster_item(r.get("Title",""), r.get("Authors","")))
        group_html = [
            '                <div class="poster-group">',
            f'                  <h5 class="poster-group-title">{html_escape(t)}</h5>',
            '                  <div class="paper-list">',
            "\n".join(items),
            '                  </div>',
            '                </div>'
        ]
        groups_html.append("\n".join(group_html))

    if not groups_html:
        return ""
    return "\n".join([
        '              <div class="program-block posters-block">',
        "\n".join(groups_html),
        '              </div>'
    ])


# ---------------------------- Slot ID generation ----------------------------

def make_slot_id(day_anchor: str, time_text: str, session_type: str, session_name: str, registry: set) -> str:
    st_slug = slugify(session_type or "")
    sn_slug = slugify(session_name or "")
    ttok = time_range_token(time_text or "")
    parts = [p for p in [day_anchor, st_slug, sn_slug or None, ttok or None] if p]
    base = "-".join(parts) if parts else day_anchor or "timeslot"
    anchor = base
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
    parts.append('                    <h6 class="paper-title">')
    if tag_class and tag_label:
        parts.append(f'                      <span class="paper-tag {tag_class}">{html_escape(tag_label)}</span>')
    parts.append(f'                      {html_escape(clean_title)}')
    parts.append('                    </h6>')
    if authors_list:
        parts.append('                    <!-- prettier-ignore -->')
        parts.append('                    <ul class="author-list">')
        for a in authors_list:
            parts.append(render_author_li(a))
        parts.append('                    </ul>')
    parts.append('                  </div>')
    return "\n".join(parts)

def render_paper_list(row):
    papers = []
    for i in range(1, 50):
        col = f"Paper {i}"
        if col in row and isinstance(row[col], str) and row[col].strip():
            papers.append(render_paper_item_from_cell(row[col]))
    return "\n".join(papers)

def render_time_slot(row, day_anchor: str, id_registry: set, posters_by_day: dict, poster_meta_by_day: dict):
    time_text = normalize_time_range(
        safe_cell_str(row, "Time (MT) ") or safe_cell_str(row, "Time (MT)")
    )
    session_type = safe_cell_str(row, "Session Type")
    session_name = safe_cell_str(row, "Session Name")
    slot_class = classify_slot(session_type)

    slot_id = make_slot_id(day_anchor, time_text, session_type, session_name, id_registry)

    # Build the <h4> (link it if it's a Poster Session and we have its letter)
    session_type_lower = (session_type or "").strip().lower()
    link_html = None
    if "poster session" in session_type_lower:
        meta = poster_meta_by_day.get(day_anchor)
        if meta:
            letter, _outfile = meta
            # Link to the stand-alone poster page (e.g., poster_session_c.html)
            link_target = f"poster_session_{letter.lower()}.html"
            link_html = f'<h4 class="slot-title"><a class="slot-link" href="{link_target}">{html_escape(session_type)}</a></h4>'

    header = []
    header.append(f'            <div id="{slot_id}" class="{slot_class}">')
    header.append('              <div class="time-slot-header">')
    header.append(f'                <span class="time-range">{html_escape(time_text or "TBD")}</span>')

    if session_type_lower.startswith("paper session"):
        header.append('                <h4 class="slot-title">')
        header.append(f'                  <span class="session-number">{html_escape(session_type)}</span>')
        header.append(f'                  <span class="session-topic">{html_escape(session_name)}</span>')
        header.append('                </h4>')
    else:
        # Use linked title if available, otherwise plain <h4>
        if link_html:
            header.append(f'                {link_html}')
        else:
            header.append(f'                <h4 class="slot-title">{html_escape(session_type)}</h4>')

    header.append('              </div>')

    blocks = []

    # Papers block
    if session_type_lower.startswith("paper session"):
        paper_html = render_paper_list(row)
        if paper_html:
            blocks.append("\n".join([
                '              <div class="program-block">',
                '                <div class="paper-list">',
                paper_html,
                '                </div>',
                '              </div>'
            ]))

    # Posters block (still externalized; leave a maintainer hint)
    if "poster session" in session_type_lower:
        meta = poster_meta_by_day.get(day_anchor)
        if meta:
            letter, outfile = meta
            # Optional: point maintainers at the HTML page too
            blocks.append(f'              <!-- Poster Session {letter} externalized to {outfile}; page: poster_session_{letter.lower()}.html -->')

    footer = ["            </div>"]
    return "\n".join(header + blocks + footer)


def render_day_section(date_str: str, rows_for_day: pd.DataFrame, prev_anchor: str, next_anchor: str, posters_by_day: dict, poster_meta_by_day: dict) -> str:
    label = parse_date_label(date_str)
    anchor = date_anchor_id(date_str)

    id_registry = set()

    html = []
    html.append(f'          <!-- {label} -->')
    html.append(f'          <section class="day-schedule" id="{anchor}">')
    html.append('            <div class="day-header-container">')
    label_short = parse_date_label_short(date_str)
    iso_attr = date_iso_attr(date_str)
    html.append('              <h3 class="day-header">')
    html.append(f'                <time datetime="{iso_attr}">')
    html.append(f'                  <span class="date-long">{label}</span>')
    html.append(f'                  <span class="date-short">{label_short}</span>')
    html.append('                </time>')
    html.append('              </h3>')
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
    html.append('            </div>')   # close .day-header-container
    for _, r in rows_for_day.iterrows():
        html.append(render_time_slot(r, anchor, id_registry, posters_by_day, poster_meta_by_day))
    html.append('          </section>')
    return "\n".join(html)

# ---------------------------- Main ----------------------------

def parse_poster_args(items):
    """
    Parse repeated --poster-csv DAY=PATH pairs into an ordered list of (day_key, DataFrame).
    DAY is one of monday/tuesday/wednesday/thursday/friday/saturday/sunday.
    """
    ordered = []
    if not items:
        return ordered
    for it in items:
        if "=" not in it:
            raise ValueError(f"--poster-csv must be DAY=PATH, got: {it}")
        day, path = it.split("=", 1)
        day_key = day.strip().lower()
        day_key = re.sub(r"[^a-z]", "", day_key)
        if day_key not in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
            raise ValueError(f"Unrecognized DAY for --poster-csv: {day}")
        dfp = load_posters_csv(path.strip())
        ordered.append((day_key, dfp))
    return ordered

def main():
    ap = argparse.ArgumentParser(description="Generate Full Schedule HTML from content CSV (authors parsed in-cell) with stable anchor IDs per time-slot. Supports Poster Session CSVs via --poster-csv DAY=PATH. Poster Sessions are externalized to poster_sessions_[a|b|c].txt in the order provided.")
    ap.add_argument("csv", help="Path to content.csv")
    ap.add_argument("-o","--output", help="Write HTML to this file (defaults to stdout)")
    ap.add_argument("--poster-csv", action="append", default=[],
                    help="Attach a poster CSV to a weekday, e.g., --poster-csv monday=/path/to/Posters-Monday.csv (repeatable)")
    args = ap.parse_args()

    # Load poster CSVs (ordered)
    posters_list = parse_poster_args(args.poster_csv)  # [(day_key, df), ...] in CLI order

    # Map day anchor names ('monday', ...) -> DataFrame for presence checks
    posters_by_day = {day: df for day, df in posters_list}

    # Hard-code output filenames in provided order: A, B, C, ...
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    def outfile_for_index(i: int) -> str:
        return f"poster_sessions_{letters[i].lower()}.txt"

    # Write each provided poster CSV to its own file
    poster_meta_by_day = {}  # day_anchor -> (letter, outfile)
    for idx, (day, dfp) in enumerate(posters_list):
        if idx >= len(letters):
            break  # safety
        letter = letters[idx]
        html_doc = render_posters_document(dfp, letter)
        outpath = outfile_for_index(idx)
        Path(outpath).write_text(html_doc, encoding="utf-8")
        poster_meta_by_day[day] = (letter, outpath)

    # Load main schedule
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
        out_lines.append(render_day_section(date, sub, prev_a, next_a, posters_by_day, poster_meta_by_day))

    html = "\n\n".join(out_lines)
    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)

if __name__ == "__main__":
    main()
