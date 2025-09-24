#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
import re
from dataclasses import dataclass
from datetime import datetime, time, date
from typing import Dict, List, Tuple, Optional, Any
import unicodedata


# ---------------- Utilities ----------------

# --- add near other small helpers (e.g., after escape_html / slugify) ---
_POSTER_RE = re.compile(r"poster\s*session\s*([A-Za-z0-9]+)", re.IGNORECASE)

def poster_session_external_href(title: str) -> Optional[str]:
    """
    If the session title looks like 'Poster Session A' (case-insensitive),
    return an external page like 'poster_session_a.html'. Otherwise None.
    """
    if not title:
        return None
    m = _POSTER_RE.search(title)
    if not m:
        return None
    key = m.group(1).lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)  # e.g., "A-1" -> "a_1"
    return f"poster_session_{key}.html"


def slugify_ascii(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
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

def time_range_token_from_display(range_text: str) -> str:
    """
    Accepts the Table's rendered time strings like '11:30 AM - 12:45 PM'
    and returns '1130-1245'. Also handles en/em dashes and single times.
    """
    if not isinstance(range_text, str):
        return ""
    s = range_text.strip()
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
    return slugify_ascii(s)

def weekday_anchor_from_date(d: Optional[date]) -> str:
    return (d.strftime("%A").lower() if d else "")


_AMPM_RE = re.compile(r"\s*([AaPp][Mm])\s*$")

def _normalize_meridiem(s: str) -> str:
    """
    Ensure meridiem is uppercase and has a preceding space:
      '3PM' -> '3 PM', '3:30pm' -> '3:30 PM'
    """
    s2 = s.strip()
    m = _AMPM_RE.search(s2)
    if not m:
        return s2
    mer = m.group(1).upper()
    # If there's no space before AM/PM, insert one.
    if len(s2) >= 3 and s2[-3] != " ":
        s2 = s2[:-len(mer)] + " " + mer
    else:
        s2 = s2[:-len(mer)] + mer
    return s2

def parse_time_piece(piece: str) -> Optional[time]:
    s = (piece or "").strip()
    if not s or s.upper() == "TBD":
        return None
    s = _normalize_meridiem(s)
    # Try 12h w/ meridiem first, then 24h.
    for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%H"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None

def parse_time_range(val: str) -> Tuple[Optional[time], Optional[time]]:
    s = (val or "").strip()
    if not s or s.upper() == "TBD":
        return (None, None)
    # Normalize dashes, then normalize each side's AM/PM spacing
    s = s.replace("–", "-").replace("—", "-")
    if "-" not in s:
        return (parse_time_piece(s), None)
    left, right = s.split("-", 1)
    left = _normalize_meridiem(left)
    right = _normalize_meridiem(right)
    return (parse_time_piece(left), parse_time_piece(right))

def fmt_time(t: Optional[time]) -> str:
    if not t:
        return ""
    return t.strftime("%-I:%M %p") if sys.platform != "win32" else t.strftime("%#I:%M %p")

def format_time_range(start: Optional[time], end: Optional[time]) -> str:
    if start and end:
        return f"{fmt_time(start)} - {fmt_time(end)}"
    if start:
        return fmt_time(start)
    return ""

def parse_date(val: str) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None

def human_day_label_from_date(d: Optional[date]) -> str:
    if not d:
        return ""
    dayname = d.strftime("%A")
    mon = d.strftime("%b")
    if sys.platform != "win32":
        return f"{dayname}, {mon}. {d.strftime('%-d')}"
    else:
        return f"{dayname}, {mon}. {d.strftime('%#d')}"

# >>> Used ONLY for anchor ID (to match the detailed-page IDs) <<<
def long_day_label_for_id(d: Optional[date]) -> str:
    if not d:
        return ""
    # e.g., "Monday, October 27, 2025"
    dayname = d.strftime("%A")
    month = d.strftime("%B")
    day = d.strftime("%-d") if sys.platform != "win32" else d.strftime("%#d")
    year = d.strftime("%Y")
    return f"{dayname}, {month} {day}, {year}"

def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )

def indent_block(text: str, level: int = 1, indent: str = "  ") -> str:
    return "\n".join((indent * level) + line if line.strip() else line for line in text.splitlines())

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

# Build a unique, full-schedule-compatible ID
# Pattern: {weekday}-{session-type}-{optional-session-name}-{HHMM-HHMM or tbd}
def make_fullschedule_anchor(day_anchor: str, time_text: str, session_type: str, session_name: str,
                             registry: set) -> str:
    st_slug = slugify_ascii(session_type or "")
    sn_slug = slugify_ascii(session_name or "")
    ttok = time_range_token_from_display(time_text or "")
    parts = [p for p in [day_anchor, st_slug, sn_slug or None, ttok or None] if p]
    base = "-".join(parts) if parts else (day_anchor or "timeslot")

    anchor = base
    i = 2
    while anchor in registry:
        anchor = f"{base}-x{i}"
        i += 1
    registry.add(anchor)
    return anchor

def session_anchor_href(s: Session, day_registry: set) -> str:
    day_anchor = weekday_anchor_from_date(s.date_d)  # 'monday', 'tuesday', ...
    # Displayed time string (e.g., '11:30 AM - 12:45 PM') -> consistent HHMM-HHMM token
    time_text = format_time_range(s.start, s.end)
    # Match full schedule: for papers use code+name; for non-papers use type only
    session_type = s.id_type                     # papers: code (e.g., "Paper Session 1A"); non-papers: title ("Coffee Break")
    session_name = s.name if s.code else ""      # only papers have a separate name

    return "#" + make_fullschedule_anchor(day_anchor, time_text, session_type, session_name, day_registry)

# ---------------- Data ----------------

@dataclass
class Session:
    date_d: Optional[date]
    # Derived label like "Monday, Oct. 27" (for display)
    day_label: str
    start: Optional[time]
    end: Optional[time]
    title: str       # non-paper title (e.g., "Coffee Break & Poster Session A") -> this is the *type* for non-papers
    code: str        # "Paper Session 1A" (this is the *type* for papers)
    name: str        # "Inclusive Mixed Reality"

    @property
    def css_class(self) -> str:
        t = (self.title or "").lower()
        c = (self.code or "").lower()
        if "paper session" in c:
            return "paper-sessions"
        if "coffee" in t or "poster" in t:
            return "break-session"
        if "lunch" in t:
            return "lunch-session"
        if "opening" in t or "keynote" in t or "conference open" in t:
            return "conference-opening"
        if "closing" in t:
            return "closing-session"
        return "special-session"

    @property
    def is_lunch(self) -> bool:
        return self.css_class == "lunch-session"

    @property
    def is_evening(self) -> bool:
        st = self.start or time(0, 0)
        return st >= time(17, 30)

    @property
    def is_morning(self) -> bool:
        st = self.start or time(0, 0)
        return st < time(12, 30)

    @property
    def is_afternoon(self) -> bool:
        return not self.is_morning and not self.is_lunch and not self.is_evening

    # The *type* and *title* used for ID generation (mirrors detailed page logic)
    @property
    def id_type(self) -> str:
        # Papers: type is the code ("Paper Session 1A"); non-papers: type is the title (e.g., "Coffee Break...")
        return self.code if self.code else self.title

    @property
    def id_title(self) -> str:
        # Papers: "{code}: {name}" ; Non-papers: just title
        if self.code:
            return f"{self.code}: {self.name}" if self.name else self.code
        return self.title

# ---------------- Core ----------------

LIKELY_TIME_KEYS = ["time", "time (mt)"]
LIKELY_TYPE_KEYS = ["session type", "type"]
LIKELY_NAME_KEYS = ["session name", "name", "track"]
LIKELY_DATE_KEYS = ["date", "day/date", "when"]

def autodetect_columns(fieldnames: List[str]) -> Dict[str, str]:
    fn_lower = {f.lower().strip(): f for f in fieldnames}

    def find_key(cands: List[str]) -> Optional[str]:
        for c in cands:
            for k in fn_lower.keys():
                if k == c or k.startswith(c):
                    return fn_lower[k]
        for c in cands:
            for k in fn_lower.keys():
                if c in k:
                    return fn_lower[k]
        return None

    col_date = find_key(LIKELY_DATE_KEYS)
    col_time = find_key(LIKELY_TIME_KEYS)
    col_type = find_key(LIKELY_TYPE_KEYS)
    col_name = find_key(LIKELY_NAME_KEYS)

    return {
        "date": col_date or "",
        "time": col_time or "",
        "type": col_type or "",
        "name": col_name or "",
    }

def load_sessions(csv_path: str, encoding: str = "utf-8") -> List[Session]:
    rows: List[Session] = []
    with open(csv_path, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header.")
        cols = autodetect_columns(reader.fieldnames)
        missing = [k for k, v in cols.items() if not v]
        if missing:
            raise ValueError(f"Could not detect columns for: {', '.join(missing)}. Found headers: {reader.fieldnames}")

        current_date_d: Optional[date] = None

        for r in reader:
            date_raw = (r.get(cols["date"], "") or "").strip()
            if date_raw:
                current_date_d = parse_date(date_raw)

            time_raw = (r.get(cols["time"], "") or "").strip()
            start, end = parse_time_range(time_raw)

            typ = (r.get(cols["type"], "") or "").strip()
            name = (r.get(cols["name"], "") or "").strip()

            # Derive paper vs non-paper
            if typ.lower().startswith("paper session"):
                code = typ
                title = ""  # handled via code+name
            else:
                code = ""
                title = typ

            label = human_day_label_from_date(current_date_d)

            # Skip blank rows (no session text)
            if not typ and not name:
                continue
            # Skip rows with no usable time (TBD/etc.) from the panoramic grid
            if not start and not end:
                continue

            rows.append(Session(current_date_d, label, start, end, title, code, name))
    return rows

def partition_by_day(sessions: List[Session]) -> Dict[str, Dict[str, List[Session]]]:
    by_day: Dict[str, List[Session]] = {}
    for s in sessions:
        by_day.setdefault(s.day_label, []).append(s)

    result: Dict[str, Dict[str, List[Session]]] = {}
    for label, lst in by_day.items():
        morning = sorted([x for x in lst if x.is_morning and not x.is_lunch],
                         key=lambda x: (x.start or time(0,0), x.end or time(0,0), x.code, x.name, x.title))
        lunch = sorted([x for x in lst if x.is_lunch],
                       key=lambda x: (x.start or time(0,0), x.end or time(0,0)))
        afternoon = sorted([x for x in lst if x.is_afternoon],
                           key=lambda x: (x.start or time(0,0), x.end or time(0,0), x.code, x.name, x.title))
        evening = sorted([x for x in lst if x.is_evening and not x.is_lunch],
                         key=lambda x: (x.start or time(0,0), x.end or time(0,0)))

        result[label] = {
            "header": label,
            "morning": morning,
            "lunch": lunch,
            "afternoon": afternoon,
            "evening": evening,
        }
    return result

def group_parallel(sessions: List[Session]) -> List[List[Session]]:
    """
    Group sessions sharing an identical time window (start,end) into parallel blocks.
    """
    buckets: Dict[Tuple[str, str], List[Session]] = {}
    def key(s: Session) -> Tuple[str, str]:
        st = (s.start or time(0,0)).strftime("%H:%M")
        en = (s.end or time(0,0)).strftime("%H:%M")
        return (st, en)
    for s in sessions:
        buckets.setdefault(key(s), []).append(s)

    groups: List[Tuple[Tuple[str, str], List[Session]]] = []
    for k, items in buckets.items():
        items_sorted = sorted(items, key=lambda x: (x.code, x.name, x.title))
        groups.append((k, items_sorted))
    groups.sort(key=lambda kv: kv[0])
    return [g for _, g in groups]


def cell_div_html(group: List[Session], day_registry: set, day_label: str) -> str:
    """
    Returns a <div class="schedule-grid-td ...">…</div> cell for the div-based grid layout.
    Adds accessible heading structure inside the cell:
      - <h3 class="time-heading"> for the time range
      - <h4 class="session-heading"> wrapping the session title
    Keeps existing aria-label summaries and visual classes.
    """
    css = group[0].css_class if group else "special-session"
    time_text = format_time_range(group[0].start, group[0].end) if group else ""

    # Build a brief, friendly ARIA label for the whole cell (kept)
    def _aria_for_session(s: Session) -> str:
        if s.code:
            if s.name:
                return f"{s.code} — {s.name}"
            return s.code
        return s.title

    aria_label_items = [_aria_for_session(s) for s in group]
    aria_label = f"{day_label}, {time_text}: " + " | ".join([x for x in aria_label_items if x])

    parts: List[str] = []
    for i, s in enumerate(group):
        show_time = (i == 0)
        href = session_anchor_href(s, day_registry)

        # Time as an h3 once per cell
        time_h3 = (
            f'<h3 class="time-heading">{escape_html(time_text)}</h3>'
            if show_time and time_text else ""
        )

        if css == "paper-sessions" and s.code:
            # Paper sessions: h4 wraps code+name
            session_h4 = (
                '<h4 class="session-heading">'
                f'<span class="session-code">{escape_html(s.code)}</span>'
                f'<span class="session-name">{escape_html(s.name)}</span>'
                '</h4>'
            )
            parts.append(
                "<div class=\"session-item\">\n"
                f"{time_h3}"
                f"  <a class=\"session-link\" href=\"{escape_html(href)}\""
                f"     aria-label=\"{escape_html(time_text + ', ' if time_text else '')}{escape_html(s.code + (': ' + s.name if s.name else ''))}\">\n"
                f"    {session_h4}\n"
                "  </a>\n"
                "</div>"
            )
        else:
            # Non-paper sessions: h4 wraps the title
            session_h4 = (
                '<h4 class="session-heading">'
                f'<span class="session-type">{escape_html(s.title)}</span>'
                '</h4>'
            )
            poster_href = poster_session_external_href(s.title)
            href = poster_href or session_anchor_href(s, day_registry)

            parts.append(
                "<div class=\"session-item\">\n"
                f"{time_h3}"
                f"  <a class=\"session-link\" href=\"{escape_html(href)}\""
                f"     aria-label=\"{escape_html(time_text + ', ' if time_text else '')}{escape_html(s.title)}\">\n"
                f"    {session_h4}\n"
                "  </a>\n"
                "</div>"
            )

        if i < len(group) - 1:
            parts.append("<div class=\"session-divider\"></div>")

    # Note: remove role=\"gridcell\" (not needed; semantic headings carry structure)
    return (
        f"<div class=\"schedule-grid-td {css}\" aria-label=\"{escape_html(aria_label)}\">\n"
        + indent_block("\n".join(parts), 1)
        + "\n</div>"
    )


def render_table(day_buckets: Dict[str, Dict[str, List[Session]]]) -> str:
    """
    Column-major DOM (day-by-day reading order) with NO inline grid placement.
    Adds semantic headings:
      - Each day header cell contains <h2 class="day-heading">
    Removes ARIA grid roles so screen readers treat this as regular content.
    """
    # 1) Order days Monday→… by actual date
    day_order: List[Tuple[Optional[date], str]] = []
    for label, dct in day_buckets.items():
        any_list = dct["morning"] or dct["lunch"] or dct["afternoon"] or dct["evening"]  # type: ignore
        d0 = any_list[0].date_d if any_list else None  # type: ignore
        day_order.append((d0, label))
    ordered_keys = [lbl for (d0, lbl) in sorted(day_order, key=lambda x: (x[0] or date.min, x[1]))]

    # 2) Per-day registries for unique anchor IDs
    day_id_registries: Dict[str, set] = {k: set() for k in ordered_keys}

    # 3) Pre-compute parallel groups per section for row alignment
    mornings = {k: group_parallel(day_buckets[k]["morning"]) for k in ordered_keys}  # type: ignore
    afternoons = {k: group_parallel(day_buckets[k]["afternoon"]) for k in ordered_keys}  # type: ignore
    evenings = {k: group_parallel(day_buckets[k]["evening"]) for k in ordered_keys}  # type: ignore

    morning_max = max((len(v) for v in mornings.values()), default=0)
    afternoon_max = max((len(v) for v in afternoons.values()), default=0)
    evening_max = max((len(v) for v in evenings.values()), default=0)

    # We always reserve exactly one lunch row for alignment
    LUNCH_ROWS = 1

    # 4) Row indices (1-based for CSS grid lines)
    ROW_HEADER = 1
    ROW_MORNING_START = ROW_HEADER + 1
    ROW_LUNCH = ROW_MORNING_START + morning_max
    ROW_AFTERNOON_START = ROW_LUNCH + LUNCH_ROWS
    ROW_EVENING_START = ROW_AFTERNOON_START + afternoon_max

    # Helper: add gc/gr classes into opening cell tag
    def _add_pos_classes(cell_html: str, col: int, row: int) -> str:
        return re.sub(
            r'^<div class="schedule-grid-td([^"]*)"',
            lambda m: f'<div class="schedule-grid-td{m.group(1)} gc-{col} gr-{row}"',
            cell_html,
            count=1
        )

    cells: List[str] = []

    # 5) Emit per-day in DOM order (column-major)
    for col_idx, k in enumerate(ordered_keys, start=1):
        header_text = str(day_buckets[k]["header"])  # type: ignore

        # Day header cell with an actual <h2>
        cells.append(
            f'<div class="schedule-grid-th gc-{col_idx} gr-{ROW_HEADER}">'
            f'<h2 class="day-heading">{escape_html(header_text)}</h2>'
            f'</div>'
        )

        # Morning rows
        mgroups = mornings[k]
        for r in range(morning_max):
            row_line = ROW_MORNING_START + r
            if r < len(mgroups) and mgroups[r]:
                cell = cell_div_html(mgroups[r], day_id_registries[k], k)
                cells.append(_add_pos_classes(cell, col_idx, row_line))
            else:
                cells.append(
                    f'<div class="schedule-grid-td empty-cell gc-{col_idx} gr-{row_line}" aria-label="Empty"></div>'
                )

        # Lunch row (first lunch per day if present)
        lunches = day_buckets[k]["lunch"]  # type: ignore
        if lunches:
            lunch_group = [sorted(lunches, key=lambda x: (x.start or time(0,0), x.end or time(0,0)))[0]]
            cell = cell_div_html(lunch_group, day_id_registries[k], k)
            cells.append(_add_pos_classes(cell, col_idx, ROW_LUNCH))
        else:
            cells.append(
                f'<div class="schedule-grid-td empty-cell gc-{col_idx} gr-{ROW_LUNCH}" aria-label="No lunch slot"></div>'
            )

        # Afternoon rows
        agroups = afternoons[k]
        for r in range(afternoon_max):
            row_line = ROW_AFTERNOON_START + r
            if r < len(agroups) and agroups[r]:
                cell = cell_div_html(agroups[r], day_id_registries[k], k)
                cells.append(_add_pos_classes(cell, col_idx, row_line))
            else:
                cells.append(
                    f'<div class="schedule-grid-td empty-cell gc-{col_idx} gr-{row_line}" aria-label="Empty"></div>'
                )

        # Evenings (if any)
        if evening_max:
            egroups = evenings[k]
            for r in range(evening_max):
                row_line = ROW_EVENING_START + r
                if r < len(egroups) and egroups[r]:
                    cell = cell_div_html(egroups[r], day_id_registries[k], k)
                    cells.append(_add_pos_classes(cell, col_idx, row_line))
                else:
                    cells.append(
                        f'<div class="schedule-grid-td empty-cell gc-{col_idx} gr-{row_line}" aria-label="Empty"></div>'
                    )

    daycount_class = f"daycount-{len(ordered_keys)}"

    # NOTE: removed role="grid" (semantic headings make this navigable)
    return (
        "<!-- Start of Schedule Grid (column-major DOM) -->\n\n"
        f'<div class="schedule-grid {daycount_class}" aria-label="Summarized schedule">\n'
        + indent_block("\n".join(cells), 1)
        + "\n</div>\n\n"
        "<!-- End of Schedule Grid -->"
    )


def main():
    ap = argparse.ArgumentParser(description="Autodetect and convert schedule CSV into ASSETS-style HTML table (with cross-links).")
    ap.add_argument("csv", help="Path to input CSV")
    ap.add_argument("-o", "--output", help="Write HTML to this file (default: stdout)")
    ap.add_argument("--encoding", default="utf-8", help="CSV file encoding (default: utf-8)")
    args = ap.parse_args()

    try:
        sessions = load_sessions(args.csv, encoding=args.encoding)
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)

    day_buckets = partition_by_day(sessions)
    html = render_table(day_buckets)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
    else:
        sys.stdout.write(html)

if __name__ == "__main__":
    main()
