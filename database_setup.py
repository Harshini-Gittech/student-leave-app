import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Users table (master users)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,      -- plain for project demo only
        role TEXT NOT NULL,          -- 'student', 'advisor', 'hod'
        class_name TEXT,
        roll_no TEXT,
        mobile TEXT
    )
    """)

    # Leave applications
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        student_name TEXT NOT NULL,
        student_class TEXT NOT NULL,
        student_roll TEXT NOT NULL,
        from_datetime TEXT NOT NULL,
        to_datetime TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',   -- pending / approved / rejected
        decided_by INTEGER,
        decided_role TEXT,
        applied_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id)
    )
    """)

    # Attendance tracker
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER UNIQUE NOT NULL,
        total_days INTEGER NOT NULL,
        leave_days INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(student_id) REFERENCES users(id)
    )
    """)

    # Insert sample users only if table empty
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    if count == 0:
        users = [
            # name, email, password, role, class_name, roll_no, mobile
            ("XYZ Student", "student@example.com", "student123", "student", "BCA 5A", "23", "9999999999"),
            ("Class Advisor", "advisor@example.com", "advisor123", "advisor", None, None, None),
            ("Head Of Department", "hod@example.com", "hod123", "hod", None, None, None),
        ]
        cur.executemany("""
            INSERT INTO users (name, email, password, role, class_name, roll_no, mobile)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, users)

        # sample attendance for the demo student
        cur.execute("SELECT id FROM users WHERE role='student' AND email='student@example.com'")
        row = cur.fetchone()
        if row:
            student_id = row[0]
            cur.execute("""
                INSERT INTO attendance (student_id, total_days, leave_days)
                VALUES (?, ?, ?)
            """, (student_id, 100, 0))

    conn.commit()
    conn.close()
    print("Database initialized with sample data.")

if __name__ == "__main__":
    init_db()
