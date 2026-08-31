"""Seed the assets table with C-MAPSS engine units."""
import os
import psycopg2
from datetime import date, timedelta

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/factorypulse",
)

ASSETS = [
    {"machine_id": f"CMAPSS_UNIT_{i}", "name": f"Turbofan Engine #{i}",
     "asset_type": "turbofan", "location": f"plant-1/bay-{(i % 5) + 1}",
     "install_date": date(2024, 1, 1) + timedelta(days=i * 7)}
    for i in range(1, 101)
]


def seed():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    for a in ASSETS:
        cur.execute(
            """
            INSERT INTO assets (machine_id, name, asset_type, location, install_date)
            VALUES (%(machine_id)s, %(name)s, %(asset_type)s, %(location)s, %(install_date)s)
            ON CONFLICT (machine_id) DO NOTHING
            """,
            a,
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {len(ASSETS)} assets.")


if __name__ == "__main__":
    seed()
