import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict

# Database setup
def get_db_connection():
    conn = sqlite3.connect(os.path.join("data", "power.db"))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS power_data (
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                is_sum BOOLEAN NOT NULL,
                capacity REAL,
                capacity_percentage REAL,
                generation REAL,
                generation_percentage REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (name, type, timestamp)
            )
        ''')
        # Create additional indexes for better query performance
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON power_data(timestamp)
        ''')

# Data model
class PowerGenerationRecord:
    def __init__(
        self,
        name: str,
        type: str,
        timestamp: str,
        is_sum: bool,
        capacity: Optional[float] = None,
        capacity_percentage: Optional[float] = None,
        generation: Optional[float] = None,
        generation_percentage: Optional[float] = None
    ):
        self.name = name
        self.type = type
        self.timestamp = timestamp
        self.is_sum = is_sum
        self.capacity = capacity
        self.capacity_percentage = capacity_percentage
        self.generation = generation
        self.generation_percentage = generation_percentage

# CRUD Operations
def insert_record(record: PowerGenerationRecord) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO power_data (
                    name, type, timestamp, is_sum,
                    capacity, capacity_percentage,
                    generation, generation_percentage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.name, record.type, record.timestamp, record.is_sum,
                record.capacity, record.capacity_percentage,
                record.generation, record.generation_percentage
            ))
        return True
    except sqlite3.IntegrityError:
        # print("Record already exists (duplicate primary key)")
        return False

def upsert_record(record: PowerGenerationRecord) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO power_data (
                    name, type, timestamp, is_sum,
                    capacity, capacity_percentage,
                    generation, generation_percentage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, type, timestamp) DO UPDATE SET
                    is_sum = excluded.is_sum,
                    capacity = excluded.capacity,
                    capacity_percentage = excluded.capacity_percentage,
                    generation = excluded.generation,
                    generation_percentage = excluded.generation_percentage
            ''', (
                record.name, record.type, record.timestamp, record.is_sum,
                record.capacity, record.capacity_percentage,
                record.generation, record.generation_percentage
            ))
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def get_record(name: str, type: str, timestamp: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM power_data
            WHERE name = ? AND type = ? AND timestamp = ?
        ''', (name, type, timestamp))
        return dict(cursor.fetchone()) if cursor.fetchone() else None

def get_records_by_time_range(start: str, end: str) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM power_data
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        ''', (start, end))
        return [dict(row) for row in cursor.fetchall()]

def get_sum_records_by_time_range(start: str, end: str) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM power_data
            WHERE timestamp BETWEEN ? AND ? AND is_sum = 1
            ORDER BY timestamp
        ''', (start, end))
        return [dict(row) for row in cursor.fetchall()]

def get_sum_records_by_time(time: str) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM power_data
            WHERE timestamp = ? AND is_sum = 1
        ''', (time, ))
        return [dict(row) for row in cursor.fetchall()]

def get_aggregated_generation_by_type(date: str) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT type, SUM(generation) as total_generation
            FROM power_data
            WHERE timestamp LIKE ? || '%' AND is_sum = 0
            GROUP BY type
        ''', (date,))
        return [dict(row) for row in cursor.fetchall()]

def delete_record(name: str, type: str, timestamp: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute('''
            DELETE FROM power_data
            WHERE name = ? AND type = ? AND timestamp = ?
        ''', (name, type, timestamp))
        return cursor.rowcount > 0

# Example usage
if __name__ == "__main__":
    # Initialize database
    init_db()

    # Sample data
    solar_record = PowerGenerationRecord(
        name="Solar Farm 1",
        type="solar",
        timestamp="2023-05-15T12:00:00",
        is_sum=False,
        capacity=150.5,
        capacity_percentage=22.1,
        generation=120.3,
        generation_percentage=18.7
    )

    wind_record = PowerGenerationRecord(
        name="Wind Park A",
        type="wind",
        timestamp="2023-05-15T12:00:00",
        is_sum=False,
        capacity=200.0,
        capacity_percentage=29.4,
        generation=180.2,
        generation_percentage=26.5
    )

    # Insert records
    insert_record(solar_record)
    upsert_record(wind_record)  # Using upsert in case it exists

    # Query examples
    print("\nAll records for May 15, 2023:")
    for record in get_records_by_time_range("2023-05-15", "2023-05-15"):
        print(record)

    print("\nAggregated generation by type on May 15, 2023:")
    for stats in get_aggregated_generation_by_type("2023-05-15"):
        print(f"{stats['type']}: {stats['total_generation']} MW")

    # Get a specific record
    print("\nSolar Farm 1 at noon:")
    print(get_record("Solar Farm 1", "solar", "2023-05-15T12:00:00"))