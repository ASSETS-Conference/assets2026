#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
import re
from dataclasses import dataclass
from datetime import datetime, time, date
from typing import Dict, List, Tuple, Optional, Any

# ---------------- Utilities ----------------

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

# ---------------- Data ----------------

@dataclass
class Session:
    date_d: Optional[date]
    # Derived label like "Monday, Oct. 27"
    day_label: str
    start: Optional[time]
    end: Optional[time]
    title: str       # non-paper title (e.g., "Coffee Break & Poster Session A")
    code: str        # "Paper Session 1A"
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

def cell_html(group: List[Session]) -> str:
    css = group[0].css_class if group else "special-session"
    parts: List[str] = []
    for i, s in enumerate(group):
        show_time = (i == 0)
        if css == "paper-sessions" and s.code:
            if show_time:
                parts.append(
                    "<div class=\"session-item\">\n"
                    f"  <span class=\"session-time\">{format_time_range(s.start, s.end)}</span>\n"
                    f"  <span class=\"session-code\">{escape_html(s.code)}</span>\n"
                    f"  <span class=\"session-name\">{escape_html(s.name)}</span>\n"
                    "</div>"
                )
            else:
                parts.append(
                    "<div class=\"session-item\">\n"
                    f"  <span class=\"session-code\">{escape_html(s.code)}</span>\n"
                    f"  <span class=\"session-name\">{escape_html(s.name)}</span>\n"
                    "</div>"
                )
        else:
            if show_time:
                parts.append(
                    "<div class=\"session-item\">\n"
                    f"  <span class=\"session-time\">{format_time_range(s.start, s.end)}</span>\n"
                    f"  <span class=\"session-type\">{escape_html(s.title)}</span>\n"
                    "</div>"
                )
            else:
                parts.append(
                    "<div class=\"session-item\">\n"
                    f"  <span class=\"session-type\">{escape_html(s.title)}</span>\n"
                    "</div>"
                )
        if i < len(group) - 1:
            parts.append("<div class=\"session-divider\"></div>")
    return "<td class=\"" + css + "\">\n" + indent_block("\n".join(parts), 2) + "\n</td>"

def render_table(day_buckets: Dict[str, Dict[str, List[Session]]]) -> str:
    # Order columns strictly by calendar date (Mon→Tue→Wed)
    day_order: List[Tuple[Optional[date], str]] = []
    for label, dct in day_buckets.items():
        any_list = dct["morning"] or dct["lunch"] or dct["afternoon"] or dct["evening"]  # type: ignore
        d0 = any_list[0].date_d if any_list else None  # type: ignore
        day_order.append((d0, label))
    ordered_keys = [lbl for (d0, lbl) in sorted(day_order, key=lambda x: (x[0] or date.min, x[1]))]

    headers = [day_buckets[k]["header"] for k in ordered_keys]  # type: ignore
    thead = "<thead>\n  <tr>\n" + "\n".join([f"    <th>{escape_html(str(h))}</th>" for h in headers]) + "\n  </tr>\n</thead>"

    def rows_for_block(block_key: str, mobile_header: Optional[str] = None) -> List[str]:
        grouped_per_day: List[List[List[Session]]] = []
        max_len = 0
        for k in ordered_keys:
            groups = group_parallel(day_buckets[k][block_key])  # type: ignore
            grouped_per_day.append(groups)
            max_len = max(max_len, len(groups))

        rows: List[str] = []
        if mobile_header:
            rows.append(
                "  <tr class=\"mobile-section-header\">\n"
                f"    <td colspan=\"{len(ordered_keys)}\">\n"
                f"      <h3>{escape_html(mobile_header)}</h3>\n"
                "    </td>\n"
                "  </tr>"
            )

        for i in range(max_len):
            tds: List[str] = []
            for groups in grouped_per_day:
                if i < len(groups):
                    tds.append(cell_html(groups[i]))
                else:
                    tds.append("<td class=\"empty-cell\"></td>")
            rows.append("  <tr>\n" + indent_block("\n".join(tds), 1) + "\n  </tr>")
        return rows

    body_rows: List[str] = []

    # Morning
    body_rows += rows_for_block("morning", mobile_header="Morning Schedule")

    # Lunch row (first lunch per day)
    lunch_tds: List[str] = []
    for k in ordered_keys:
        lunches = day_buckets[k]["lunch"]  # type: ignore
        if lunches:
            lunch_group = [sorted(lunches, key=lambda x: (x.start or time(0,0), x.end or time(0,0)))[0]]
            lunch_tds.append(cell_html(lunch_group))
        else:
            lunch_tds.append("<td class=\"empty-cell\"></td>")
    body_rows.append("  <tr>\n" + indent_block("\n".join(lunch_tds), 1) + "\n  </tr>")

    # Afternoon
    body_rows += rows_for_block("afternoon", mobile_header="Afternoon Schedule")

    # Evening (with header)
    if any(day_buckets[k]["evening"] for k in ordered_keys):  # type: ignore
        body_rows += rows_for_block("evening", mobile_header="Evening Schedule")

    tbody = "<tbody>\n" + "\n".join(body_rows) + "\n</tbody>"
    return ("<!-- Start of Schedule Table -->\n\n"
            "<table class=\"schedule-table\">\n"
            + indent_block(thead, 1) + "\n"
            + indent_block(tbody, 1) + "\n"
            "</table>\n\n"
            "<!-- End of Schedule Table -->")

def main():
    ap = argparse.ArgumentParser(description="Autodetect and convert schedule CSV into ASSETS-style HTML table.")
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
