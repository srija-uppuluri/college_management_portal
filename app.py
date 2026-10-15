import os
import sqlite3
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "local_classroom-demo-key"
)

# Project directory
BASE_DIR = Path(__file__).resolve().parent

# Database location
DATABASE_PATH = Path(
    os.environ.get(
        "DATABASE_PATH",
        str(BASE_DIR / "instance" / "events.db")
    )
)

# Available college events
EVENTS = [
    "code sprints",
    "AI hackathon",
    "web creation",
    "cyber security seminars",
    "robotics competition"
]


# Database connection
def get_db():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


# Initialize the database
def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                department TEXT NOT NULL,
                year TEXT NOT NULL,
                event TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Registered',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email, event)
            )
        """)

        db.commit()


# Initialize database when the application starts
init_db()


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM registrations"
        ).fetchone()[0]

        event_counts = db.execute(
            "SELECT COUNT(DISTINCT event) FROM registrations"
        ).fetchone()[0]

    return render_template(
        "index.html",
        total=total,
        event_counts=event_counts,
        events=EVENTS
    )


# --------------------------------------------------
# REGISTRATION PAGE
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        department = request.form.get(
            "department", ""
        ).strip()

        year = request.form.get(
            "year", ""
        ).strip()

        event = request.form.get(
            "event", ""
        ).strip()

        # Validate required fields
        if not all([
            name,
            email,
            department,
            year,
            event
        ]):
            flash(
                "Please fill in all fields.",
                "error"
            )

            return redirect(url_for("register"))

        # Validate email
        if (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):
            flash(
                "Please enter a valid email address.",
                "error"
            )

            return redirect(url_for("register"))

        # Validate event
        if event not in EVENTS:
            flash(
                "Please select a valid event.",
                "error"
            )

            return redirect(url_for("register"))

        # Validate academic year
        valid_years = [
            "1st Year",
            "2nd Year",
            "3rd Year",
            "4th Year"
        ]

        if year not in valid_years:
            flash(
                "Please select a valid year.",
                "error"
            )

            return redirect(url_for("register"))

        # Save registration
        try:
            with get_db() as db:

                db.execute("""
                    INSERT INTO registrations
                    (
                        name,
                        email,
                        department,
                        year,
                        event
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    name,
                    email,
                    department,
                    year,
                    event
                ))

                db.commit()

            flash(
                "Registration successful!",
                "success"
            )

        except sqlite3.IntegrityError:
            flash(
                "This email has already registered for this event.",
                "error"
            )

        return redirect(url_for("register"))

    return render_template(
        "register.html",
        events=EVENTS
    )


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

@app.route("/admin")
def admin():

    search = request.args.get(
        "search", ""
    ).strip()

    status_filter = request.args.get(
        "status", ""
    ).strip()

    query = """
        SELECT *
        FROM registrations
        WHERE 1=1
    """

    params = []

    # Search by name, email, department, year, or event
    if search:

        query += """
            AND (
                name LIKE ?
                OR email LIKE ?
                OR department LIKE ?
                OR year LIKE ?
                OR event LIKE ?
            )
        """

        pattern = f"%{search}%"

        params.extend([
            pattern,
            pattern,
            pattern,
            pattern,
            pattern
        ])

    # Filter by registration status
    valid_statuses = [
        "Registered",
        "Attended",
        "Cancelled"
    ]

    if status_filter in valid_statuses:

        query += " AND status = ?"

        params.append(status_filter)

    query += " ORDER BY created_at DESC"

    with get_db() as db:

        # Get filtered registrations
        registrations = db.execute(
            query,
            params
        ).fetchall()

        # Total registrations
        total = db.execute(
            "SELECT COUNT(*) FROM registrations"
        ).fetchone()[0]

        # Registered participants
        registered = db.execute(
            """
            SELECT COUNT(*)
            FROM registrations
            WHERE status = ?
            """,
            ("Registered",)
        ).fetchone()[0]

        # Attended participants
        attended = db.execute(
            """
            SELECT COUNT(*)
            FROM registrations
            WHERE status = ?
            """,
            ("Attended",)
        ).fetchone()[0]

        # Event-wise statistics
        event_stats = db.execute("""
            SELECT
                event,
                COUNT(*) AS total
            FROM registrations
            GROUP BY event
            ORDER BY event
        """).fetchall()

    return render_template(
        "admin.html",
        registrations=registrations,
        total=total,
        registered=registered,
        attended=attended,
        event_stats=event_stats,
        search=search,
        status_filter=status_filter
    )


# --------------------------------------------------
# UPDATE REGISTRATION STATUS
# --------------------------------------------------

@app.route(
    "/admin/status/<int:registration_id>",
    methods=["POST"]
)
def update_status(registration_id):

    status = request.form.get(
        "status", ""
    ).strip()

    valid_statuses = [
        "Registered",
        "Attended",
        "Cancelled"
    ]

    if status not in valid_statuses:

        flash(
            "Invalid registration status.",
            "error"
        )

        return redirect(url_for("admin"))

    with get_db() as db:

        result = db.execute(
            """
            UPDATE registrations
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                registration_id
            )
        )

        db.commit()

        if result.rowcount:

            flash(
                "Registration status updated successfully.",
                "success"
            )

        else:

            flash(
                "Registration not found.",
                "error"
            )

    return redirect(url_for("admin"))


# --------------------------------------------------
# DELETE REGISTRATION
# --------------------------------------------------

@app.route(
    "/admin/delete/<int:registration_id>",
    methods=["POST"]
)
def delete_registration(registration_id):

    with get_db() as db:

        result = db.execute(
            """
            DELETE FROM registrations
            WHERE id = ?
            """,
            (registration_id,)
        )

        db.commit()

        if result.rowcount:

            flash(
                "Registration deleted successfully.",
                "success"
            )

        else:

            flash(
                "Registration not found.",
                "error"
            )

    return redirect(url_for("admin"))


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():

    try:

        with get_db() as db:
            db.execute("SELECT 1")

        return jsonify(
            status="ok",
            application="Management portal"
        )

    except sqlite3.Error:

        return jsonify(
            status="error"
        ), 500


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )