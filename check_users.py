import sqlite3

# Connect to your database
conn = sqlite3.connect("database.db")
c = conn.cursor()

# Fetch all users
c.execute("SELECT id, name, email, role FROM users")
users = c.fetchall()

# Print all users
print("All users in database:")
for user in users:
    print(f"ID: {user[0]}, Name: {user[1]}, Email: {user[2]}, Role: {user[3]}")

# Close the connection
conn.close()
