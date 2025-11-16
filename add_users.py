import sqlite3
from werkzeug.security import generate_password_hash

# Connect to database
conn = sqlite3.connect("database.db")
c = conn.cursor()

# Add sample users

# Student login
c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
          ("Student One", "student@test.com", generate_password_hash("1234"), "student"))

# Advisor login
c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
          ("Advisor One", "advisor@test.com", generate_password_hash("1234"), "advisor"))

# HOD login
c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
          ("HOD One", "hod@test.com", generate_password_hash("1234"), "hod"))

# Save and close
conn.commit()
conn.close()

print("Users added successfully!")
