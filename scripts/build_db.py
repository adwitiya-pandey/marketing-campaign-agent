"""Build deterministic customer SQLite database."""

from __future__ import annotations

import argparse
import random
import sqlite3
from pathlib import Path

SCHEMA = """
DROP TABLE IF EXISTS purchases;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS segments;

CREATE TABLE segments(
    segment TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE customers(
    customer_id INTEGER PRIMARY KEY,
    segment TEXT NOT NULL REFERENCES segments(segment),
    age_band TEXT NOT NULL CHECK(age_band IN ('18-24','25-34','35-44','45-54','55+')),
    region TEXT NOT NULL CHECK(region IN ('North','South','East','West')),
    income_band TEXT NOT NULL CHECK(income_band IN ('low','mid','high')),
    interest TEXT NOT NULL,
    lifetime_value REAL NOT NULL CHECK(lifetime_value>=0),
    email_opt_in INTEGER NOT NULL CHECK(email_opt_in IN (0,1))
);

CREATE TABLE purchases(
    purchase_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    category TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount>0),
    purchase_month TEXT NOT NULL
);
"""

SEGMENTS_DATA = [
    (
        "fitness-enthusiasts",
        "Active individuals interested in sports, workout gear, and health tracking",
    ),
    (
        "young-professionals",
        "Career-focused urban workers interested in efficiency, productivity, and modern lifestyle",
    ),
    (
        "eco-conscious-families",
        "Households prioritizing sustainability, eco-friendly products, and organic living",
    ),
    ("students", "College and university students seeking budget-friendly, versatile essentials"),
]

AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55+"]
REGIONS = ["North", "South", "East", "West"]
INCOME_BANDS = ["low", "mid", "high"]
INTERESTS_BY_SEGMENT = {
    "fitness-enthusiasts": ["running", "cycling", "strength training", "yoga", "triathlon"],
    "young-professionals": [
        "tech gadgets",
        "commute gear",
        "minimalism",
        "productivity",
        "specialty coffee",
    ],
    "eco-conscious-families": [
        "zero waste",
        "organic gardening",
        "outdoor recreation",
        "meal prep",
        "sustainability",
    ],
    "students": ["budget lifestyle", "campus study", "snacking", "dorm organization", "fitness"],
}
CATEGORIES = [
    "Hydration Gear",
    "Footwear",
    "Containers & Storage",
    "Outdoor Accessories",
    "Wellness",
]
MONTHS = [f"2026-0{i}" for i in range(1, 10)]


def build_database(out_path: Path | str, seed: int = 42) -> None:
    """Build customers database deterministically using provided random seed."""
    rng = random.Random(seed)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    conn = sqlite3.connect(str(target))
    try:
        conn.executescript(SCHEMA)

        # 1. Insert segments
        conn.executemany("INSERT INTO segments VALUES (?, ?)", SEGMENTS_DATA)

        # 2. Insert 2,000 customers (strictly demographic & behavioural, no identifiers)
        customers = []
        for cid in range(1, 2001):
            segment = SEGMENTS_DATA[cid % len(SEGMENTS_DATA)][0]
            age_band = rng.choice(AGE_BANDS)
            region = rng.choice(REGIONS)
            income_band = rng.choice(INCOME_BANDS)
            interest = rng.choice(INTERESTS_BY_SEGMENT[segment])
            ltv = round(rng.uniform(15.0, 1500.0), 2)
            email_opt = rng.choice([0, 1])
            customers.append(
                (cid, segment, age_band, region, income_band, interest, ltv, email_opt)
            )

        conn.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            customers,
        )

        # 3. Insert purchases
        purchases = []
        pid = 1
        for cid in range(1, 2001):
            num_purchases = rng.randint(1, 5)
            for _ in range(num_purchases):
                cat = rng.choice(CATEGORIES)
                amt = round(rng.uniform(10.0, 350.0), 2)
                mth = rng.choice(MONTHS)
                purchases.append((pid, cid, cat, amt, mth))
                pid += 1

        conn.executemany(
            "INSERT INTO purchases VALUES (?, ?, ?, ?, ?)",
            purchases,
        )

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build customer SQLite database.")
    parser.add_argument("--out", default="data/customers.db", help="Path to output database file")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    args = parser.parse_args()
    build_database(args.out, seed=args.seed)
    print(f"Database built successfully at {args.out} with seed {args.seed}")


if __name__ == "__main__":
    main()
