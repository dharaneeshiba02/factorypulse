"""Seed the local database with repeatable FactoryPulse demo records."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import bcrypt
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://factorypulse:change-me-local-only@localhost:5432/factorypulse",
)

MACHINES = [
    ("CNC-07", "CNC Mill 07", "CNC_Mill", "Plant A / Bay 3", date(2021, 3, 15)),
    ("CNC-12", "CNC Mill 12", "CNC_Mill", "Plant A / Bay 5", date(2020, 8, 22)),
    ("TURB-01", "Turbofan 01", "Turbofan", "Plant B / Engine Bay", date(2019, 11, 1)),
    ("TURB-02", "Turbofan 02", "Turbofan", "Plant B / Engine Bay", date(2020, 2, 14)),
    ("BRG-04", "Bearing Rig 04", "Bearing_Rig", "Plant A / Test Lab", date(2022, 1, 10)),
    (
        "PUMP-09",
        "Centrifugal Pump 09",
        "Centrifugal_Pump",
        "Plant C / Utility",
        date(2021, 7, 20),
    ),
]

SENSORS = [
    ("temperature", "C", -40.0, 400.0),
    ("vibration", "mm/s", 0.0, 50.0),
    ("pressure", "bar", 0.0, 500.0),
    ("rpm", "rpm", 0.0, 50_000.0),
    ("current", "A", 0.0, 200.0),
]

USERS = [
    ("tech_arun", "arun.technician@example.local", "technician", "Arun Kumar"),
    ("eng_priya", "priya.engineer@example.local", "engineer", "Priya Sharma"),
    ("mgr_raj", "raj.manager@example.local", "manager", "Raj Patel"),
    (
        "ds_meera",
        "meera.data-scientist@example.local",
        "data_scientist",
        "Meera Nair",
    ),
    ("admin_sys", "admin@example.local", "admin", "System Admin"),
]

MACHINE_CLASS_DESCRIPTIONS = {
    "CNC_Mill": "Computer numerical control milling machine",
    "Turbofan": "Turbofan engine",
    "Bearing_Rig": "Bearing test rig",
    "Centrifugal_Pump": "Centrifugal pump",
}


def seed() -> None:
    """Insert demo assets and users without duplicating existing records."""
    demo_password = os.environ.get("DEMO_USER_PASSWORD", "")
    if len(demo_password) < 12 or demo_password.startswith("replace-with-"):
        raise RuntimeError(
            "Set DEMO_USER_PASSWORD in .env to a local password of at least "
            "12 characters before seeding demo users; replace the example value."
        )

    password_hash = bcrypt.hashpw(
        demo_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("ascii")

    with psycopg2.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            for machine_class, description in MACHINE_CLASS_DESCRIPTIONS.items():
                cursor.execute(
                    """
                    INSERT INTO machine_classes (machine_class, description)
                    VALUES (%s, %s)
                    ON CONFLICT (machine_class) DO NOTHING
                    """,
                    (machine_class, description),
                )

            for machine_id, name, machine_class, location, install_date in MACHINES:
                cursor.execute(
                    """
                    INSERT INTO assets
                        (machine_id, name, machine_class, asset_type, location, install_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (machine_id) DO NOTHING
                    """,
                    (
                        machine_id,
                        name,
                        machine_class,
                        machine_class,
                        location,
                        install_date,
                    ),
                )

                for sensor, unit, minimum, maximum in SENSORS:
                    cursor.execute(
                        """
                        INSERT INTO sensors
                            (sensor_id, machine_id, sensor, unit, min_valid, max_valid)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sensor_id) DO NOTHING
                        """,
                        (
                            f"{machine_id}_{sensor}",
                            machine_id,
                            sensor,
                            unit,
                            minimum,
                            maximum,
                        ),
                    )

            for username, email, role, full_name in USERS:
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, full_name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    (username, email, password_hash, role, full_name),
                )

    print(
        f"Seed complete: {len(MACHINES)} machines, "
        f"{len(MACHINES) * len(SENSORS)} sensors, {len(USERS)} demo users."
    )


if __name__ == "__main__":
    seed()
