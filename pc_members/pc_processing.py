#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict

# example usage: python3 pc_processing.py pc_members.csv > pc_members.txt


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <csv_file>".format(sys.argv[0]))
        sys.exit(1)

    csv_file = sys.argv[1]
    groups = defaultdict(list)

    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Strip whitespace from header field names
        reader.fieldnames = [field.strip() for field in reader.fieldnames]
        for row in reader:
            # Also trim each value in the row
            row = {k.strip(): v.strip() for k, v in row.items()}
            name = row["Name"]
            if not name:
                continue
            first_letter = name[0].upper()
            groups[first_letter].append(row)

    for letter in sorted(groups.keys()):
        print(f"<h2>{letter}</h2>")
        print('<ul class="pc-members">')
        for row in sorted(groups[letter], key=lambda r: r["Name"]):
            name = row["Name"]
            affiliation = row["Affiliation"]
            country = row["Country"]
            print(f'  <li class="pc-member"><span class="pc-name">{name},</span> <span class="pc-institution">{affiliation},</span> <span class="pc-country">{country}.</span></li>')
        print("</ul>")

if __name__ == "__main__":
    main()
