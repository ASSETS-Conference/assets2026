import pandas as pd
from html import escape



def count(df: pd.DataFrame) -> str:
    # Validate columns
    for col in ("Type", "Title", "Authors"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    all_authors = pd.DataFrame({'authors': []})
    for _, row in df.iterrows():
        authors_raw = str(row["Authors"]).strip()

        # Split authors by semicolon (keeps commas inside names)
        authors = pd.DataFrame({'authors':[escape(a.strip()) for a in authors_raw.split(";") if a.strip()]})
        all_authors = pd.concat([all_authors, authors])

    authors = all_authors.value_counts()


def main():

    df = pd.read_csv("./accepted.csv")
    count(df)


if __name__ == "__main__":
    main()
