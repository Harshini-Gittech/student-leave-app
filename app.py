from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta, date
import os

app = Flask(__name__)
app.secret_key = "super-secret-key-just-for-project"

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


# ---------- Helpers ----------

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def calculate_leave_days(start_str, end_str):
    start = datetime.fromisoformat(start_str)
    end = datetime.fromisoformat(end_str)
    days = (end.date() - start.date()).days + 1
    return max(days, 1)

@app.context_processor
def inject_today():
    return {"today_date": date.today()}


# ---------- Home ----------

@app.route("/")
def index():
    if "user_id" in session:
        role = session.get("role")
        if role == "student":
            return redirect(url_for("student_dashboard"))
        elif role == "advisor":
            return redirect(url_for("advisor_dashboard"))
        elif role == "hod":
            return redirect(url_for("hod_dashboard"))
    return render_template("index.html")


# ---------- Auth: Register / Login / Logout ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    # Student self-registration
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        confirm = request.form["confirm_password"].strip()
        mobile = request.form["mobile"].strip()
        class_name = request.form["class_name"].strip()
        roll_no = request.form["roll_no"].strip()

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if not full_name or not email or not password or not mobile:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("Email is already registered. Please login.", "danger")
            return redirect(url_for("login"))

        # Insert new student
        conn.execute("""
            INSERT INTO users (name, email, password, role, class_name, roll_no, mobile)
            VALUES (?, ?, ?, 'student', ?, ?, ?)
        """, (full_name, email, password, class_name, roll_no, mobile))

        # Get new student id
        student_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]

        # Default attendance: 100 total days, 0 leave used
        conn.execute("""
            INSERT INTO attendance (student_id, total_days, leave_days)
            VALUES (?, ?, ?)
        """, (student_id, 100, 0))

        conn.commit()
        conn.close()

        flash("Registration successful. You can now login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            flash("Login successful", "success")

            if user["role"] == "student":
                return redirect(url_for("student_dashboard"))
            elif user["role"] == "advisor":
                return redirect(url_for("advisor_dashboard"))
            elif user["role"] == "hod":
                return redirect(url_for("hod_dashboard"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ---------- Student side ----------

@app.route("/student/dashboard")
def student_dashboard():
    user = get_current_user()
    if not user or user["role"] != "student":
        return redirect(url_for("login"))

    conn = get_db_connection()
    leaves = conn.execute("""
        SELECT * FROM leaves
        WHERE student_id = ?
        ORDER BY applied_at DESC
    """, (user["id"],)).fetchall()

    attendance = conn.execute("""
        SELECT total_days, leave_days FROM attendance
        WHERE student_id = ?
    """, (user["id"],)).fetchone()
    conn.close()

    return render_template(
        "student_dashboard.html",
        user=user,
        leaves=leaves,
        attendance=attendance
    )


@app.route("/apply-leave", methods=["GET", "POST"])
def apply_leave():
    user = get_current_user()
    if not user or user["role"] != "student":
        return redirect(url_for("login"))

    letter_preview = None

    if request.method == "POST":
        student_name = request.form["student_name"].strip()
        student_class = request.form["student_class"].strip()
        student_roll = request.form["student_roll"].strip()
        letter_date_raw = request.form["letter_date"].strip()

        from_dt = request.form["from_datetime"]
        to_dt = request.form["to_datetime"]
        reason = request.form["reason"].strip()

        # 5-hour rule
        try:
            from_dt_obj = datetime.fromisoformat(from_dt)
        except ValueError:
            flash("Invalid From Date/Time.", "danger")
            return redirect(url_for("apply_leave"))

        now = datetime.now()
        if from_dt_obj - now < timedelta(hours=5):
            flash("Leave must be applied at least 5 hours before start time.", "danger")
            return redirect(url_for("apply_leave"))

        # 25% attendance rule
        conn = get_db_connection()
        attendance = conn.execute("""
            SELECT total_days, leave_days FROM attendance
            WHERE student_id = ?
        """, (user["id"],)).fetchone()

        if not attendance:
            flash("Attendance record missing for this student.", "danger")
            conn.close()
            return redirect(url_for("apply_leave"))

        total_days = attendance["total_days"]
        leave_days_used = attendance["leave_days"]
        new_leave_days = calculate_leave_days(from_dt, to_dt)

        if leave_days_used + new_leave_days > 0.25 * total_days:
            flash("Leave limit exceeded (max 25% of total working days).", "danger")
            conn.close()
            return redirect(url_for("apply_leave"))

        # Insert leave
        applied_at = now.isoformat(timespec="minutes")
        conn.execute("""
            INSERT INTO leaves (
                student_id,
                student_name,
                student_class,
                student_roll,
                from_datetime,
                to_datetime,
                reason,
                status,
                applied_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            user["id"],
            student_name,
            student_class,
            student_roll,
            from_dt,
            to_dt,
            reason,
            applied_at
        ))
        conn.commit()
        conn.close()

        from_date_display = from_dt_obj.strftime("%d-%m-%Y")
        to_date_display = datetime.fromisoformat(to_dt).strftime("%d-%m-%Y")

        try:
            letter_date_display = datetime.strptime(
                letter_date_raw, "%Y-%m-%d"
            ).strftime("%d-%m-%Y")
        except ValueError:
            letter_date_display = now.strftime("%d-%m-%Y")

        letter_preview = {
            "name": student_name,
            "class_name": student_class,
            "roll_no": student_roll,
            "from_date": from_date_display,
            "to_date": to_date_display,
            "reason": reason,
            "today": letter_date_display,
        }

        flash("Leave applied successfully. Waiting for approval.", "success")

    return render_template("apply_leave.html", user=user, letter=letter_preview)


# ---------- Shared helper: filtered leaves ----------

def get_filtered_leaves(status_filter: str | None, class_filter: str | None):
    conn = get_db_connection()

    query = "SELECT * FROM leaves"
    conditions = []
    params = []

    if status_filter and status_filter != "all":
        conditions.append("status = ?")
        params.append(status_filter)

    if class_filter and class_filter != "all":
        conditions.append("student_class = ?")
        params.append(class_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY applied_at DESC"

    leaves = conn.execute(query, params).fetchall()
    classes = conn.execute("""
        SELECT DISTINCT student_class
        FROM leaves
        WHERE student_class IS NOT NULL AND student_class != ''
        ORDER BY student_class
    """).fetchall()

    conn.close()
    return leaves, classes


# ---------- Advisor & HOD dashboards ----------

@app.route("/advisor/dashboard")
def advisor_dashboard():
    user = get_current_user()
    if not user or user["role"] != "advisor":
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "all")
    class_filter = request.args.get("cls", "all")

    leaves, classes = get_filtered_leaves(status_filter, class_filter)

    return render_template(
        "advisor_dashboard.html",
        user=user,
        leaves=leaves,
        classes=classes,
        selected_status=status_filter,
        selected_class=class_filter
    )


@app.route("/hod/dashboard")
def hod_dashboard():
    user = get_current_user()
    if not user or user["role"] != "hod":
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "all")
    class_filter = request.args.get("cls", "all")

    leaves, classes = get_filtered_leaves(status_filter, class_filter)

    return render_template(
        "hod_dashboard.html",
        user=user,
        leaves=leaves,
        classes=classes,
        selected_status=status_filter,
        selected_class=class_filter
    )


# ---------- Advisor: view letter ----------

@app.route("/advisor/leave/<int:leave_id>")
def advisor_view_leave(leave_id):
    user = get_current_user()
    if not user or user["role"] != "advisor":
        return redirect(url_for("login"))

    conn = get_db_connection()
    leave = conn.execute("SELECT * FROM leaves WHERE id = ?", (leave_id,)).fetchone()
    conn.close()

    if not leave:
        flash("Leave application not found.", "danger")
        return redirect(url_for("advisor_dashboard"))

    from_date = datetime.fromisoformat(leave["from_datetime"]).strftime("%d-%m-%Y")
    to_date = datetime.fromisoformat(leave["to_datetime"]).strftime("%d-%m-%Y")

    letter_date = leave["applied_at"][:10]
    try:
        letter_date = datetime.strptime(letter_date, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        pass

    return render_template(
        "advisor_view_letter.html",
        user=user,
        leave=leave,
        from_date=from_date,
        to_date=to_date,
        letter_date=letter_date,
    )


# ---------- Approve / Reject ----------

@app.route("/leave/update", methods=["POST"])
def update_leave():
    user = get_current_user()
    if not user or user["role"] != "advisor":
        return redirect(url_for("login"))

    leave_id = request.form["leave_id"]
    action = request.form["action"]

    conn = get_db_connection()
    leave = conn.execute("SELECT * FROM leaves WHERE id = ?", (leave_id,)).fetchone()

    if not leave:
        conn.close()
        flash("Leave not found.", "danger")
        return redirect(url_for("advisor_dashboard"))

    if action == "approve":
        conn.execute("""
            UPDATE leaves
            SET status = 'approved', decided_by = ?, decided_role = ?
            WHERE id = ?
        """, (user["id"], user["role"], leave_id))

        days = calculate_leave_days(leave["from_datetime"], leave["to_datetime"])
        conn.execute("""
            UPDATE attendance
            SET leave_days = leave_days + ?
            WHERE student_id = ?
        """, (days, leave["student_id"]))

        flash("Leave approved.", "success")

    elif action == "reject":
        conn.execute("""
            UPDATE leaves
            SET status = 'rejected', decided_by = ?, decided_role = ?
            WHERE id = ?
        """, (user["id"], user["role"], leave_id))
        flash("Leave rejected.", "info")

    conn.commit()
    conn.close()

    return redirect(url_for("advisor_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
