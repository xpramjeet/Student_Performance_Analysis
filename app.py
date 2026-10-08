from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, session
from dotenv import load_dotenv
from flask import send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import os

load_dotenv()
import mysql.connector
import io
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, send_file
from flask import Flask, render_template, request, redirect, session, send_file
app = Flask(__name__)
app.secret_key = "student_performance_secret_key"

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl_disabled=False
    )


# =========================
# HOME / LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")

@app.route("/add-certificate", methods=["GET", "POST"])
def add_certificate():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    message = None
    error = None

    if request.method == "POST":

        student_id = request.form["student_id"]
        certificate_title = request.form["certificate_title"]

        certificate_file = request.files.get("certificate_file")

        if not student_id:
            error = "Please select a student."

        elif not certificate_title:
            error = "Please enter certificate title."

        elif not certificate_file or certificate_file.filename == "":
            error = "Please select a PDF certificate."

        elif not certificate_file.filename.lower().endswith(".pdf"):
            error = "Only PDF files are allowed."

        else:

            file_data = certificate_file.read()

            cursor.execute("""
                INSERT INTO student_certificates
                (
                    student_id,
                    certificate_title,
                    file_name,
                    file_data
                )
                VALUES (%s, %s, %s, %s)
            """, (
                student_id,
                certificate_title,
                certificate_file.filename,
                file_data
            ))

            db.commit()

            message = "Certificate uploaded successfully."

    cursor.execute("""
        SELECT
            id,
            student_name,
            roll_no
        FROM students
        ORDER BY student_name
    """)

    students = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_certificate.html",
        students=students,
        message=message,
        error=error
    )
    
@app.route("/student-certificates")
def student_certificates():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            certificate_title,
            file_name,
            uploaded_at
        FROM student_certificates
        WHERE student_id = %s
        ORDER BY uploaded_at DESC
    """, (student_id,))

    certificates = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_certificates.html",
        certificates=certificates
    )
    
    
    
    
@app.route("/student-certificate-download/<int:certificate_id>")
def student_certificate_download(certificate_id):

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            file_name,
            file_data
        FROM student_certificates
        WHERE id = %s
        AND student_id = %s
    """, (certificate_id, student_id))

    certificate = cursor.fetchone()

    cursor.close()
    db.close()

    if not certificate:
        return "Certificate not found or access denied.", 404

    return send_file(
        io.BytesIO(certificate["file_data"]),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=certificate["file_name"]
    )

@app.route("/student-login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                student_users.id,
                student_users.student_id,
                student_users.username,
                student_users.password,
                students.student_name,
                students.roll_no
            FROM student_users
            JOIN students
            ON student_users.student_id = students.id
            WHERE student_users.username = %s
        """, (username,))

        student = cursor.fetchone()

        cursor.close()
        db.close()

        if student and check_password_hash(
            student["password"],
            password
        ):

            session["student_user_id"] = student["id"]
            session["student_id"] = student["student_id"]
            session["student_username"] = student["username"]
            session["student_name"] = student["student_name"]
            session["student_roll_no"] = student["roll_no"]

            return redirect("/student-dashboard")

        return render_template(
            "student_login.html",
            error="Invalid username or password"
        )

    return render_template("student_login.html")


    
@app.route("/student-dashboard")
def student_dashboard():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS unread_count
        FROM student_messages
        WHERE student_id = %s
        AND is_read = FALSE
    """, (student_id,))

    result = cursor.fetchone()

    unread_count = result["unread_count"]

    cursor.close()
    db.close()

    return render_template(
        "student_dashboard.html",
        student_name=session.get("student_name"),
        student_roll_no=session.get("student_roll_no"),
        unread_count=unread_count
    )

@app.route("/student-profile")
def student_profile():

    if "student_id" not in session:
        return redirect("/student-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name,
            course,
            semester,
            email,
            phone
        FROM students
        WHERE id = %s
    """, (session["student_id"],))

    student = cursor.fetchone()

    cursor.close()
    db.close()

    if not student:
        return "Student profile not found"

    return render_template(
        "student_profile.html",
        student=student
    )
    
@app.route("/student-marks")
def student_marks():

    if "student_id" not in session:
        return redirect("/student-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            marks.id,
            marks.subject,
            marks.marks,
            marks.max_marks
        FROM marks
        WHERE marks.student_id = %s
        ORDER BY marks.subject
    """, (session["student_id"],))

    marks_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_marks.html",
        marks=marks_data
    )
    
@app.route("/student-practical")
def student_practical():

    if "student_id" not in session:
        return redirect("/student-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            practical.id,
            practical.subject,
            practical.marks,
            practical.max_marks
        FROM practical
        WHERE practical.student_id = %s
        ORDER BY practical.subject
    """, (session["student_id"],))

    practical_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_practical.html",
        practical=practical_data
    )
@app.route("/student-assignments")
def student_assignments():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            a.id,
            a.title,
            a.subject,
            a.marks,
            a.max_marks,
            a.submission_status,

            s.id AS submission_id,
            s.file_name,
            s.submitted_at,
            s.status AS file_submission_status,
            s.feedback

        FROM assignments a

        LEFT JOIN assignment_submissions s
            ON a.id = s.assignment_id
            AND s.student_id = %s

        WHERE a.student_id = %s

        ORDER BY a.id DESC
    """, (student_id, student_id))

    assignment_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_assignments.html",
        assignments=assignment_data
    )

@app.route("/student-submit-assignment/<int:assignment_id>", methods=["POST"])
def student_submit_assignment(assignment_id):

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    submitted_file = request.files.get("assignment_file")

    if not submitted_file or submitted_file.filename == "":
        return "Please select a file.", 400

    allowed_extensions = [".pdf", ".doc", ".docx"]

    if not any(
        submitted_file.filename.lower().endswith(ext)
        for ext in allowed_extensions
    ):
        return "Only PDF, DOC and DOCX files are allowed.", 400

    file_data = submitted_file.read()

    db = get_db_connection()
    cursor = db.cursor()

    # Check whether student already submitted this assignment
    cursor.execute("""
        SELECT id
        FROM assignment_submissions
        WHERE assignment_id = %s
        AND student_id = %s
    """, (assignment_id, student_id))

    existing = cursor.fetchone()

    if existing:
        cursor.close()
        db.close()
        return "You have already submitted this assignment.", 400

    cursor.execute("""
        INSERT INTO assignment_submissions
        (
            assignment_id,
            student_id,
            file_name,
            file_data
        )
        VALUES (%s, %s, %s, %s)
    """, (
        assignment_id,
        student_id,
        submitted_file.filename,
        file_data
    ))

    db.commit()

    cursor.close()
    db.close()

    return redirect("/student-assignments")

@app.route("/assignment-submissions")
def assignment_submissions():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            s.id,
            s.file_name,
            s.submitted_at,
            s.status,
            s.feedback,
            st.student_name,
            st.roll_no,
            a.title AS assignment_title,
            a.subject
        FROM assignment_submissions s
        JOIN students st
            ON s.student_id = st.id
        JOIN assignments a
            ON s.assignment_id = a.id
        ORDER BY s.submitted_at DESC
    """)

    submissions = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "assignment_submissions.html",
        submissions=submissions
    )

@app.route("/assignment-submission-download/<int:submission_id>")
def assignment_submission_download(submission_id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            file_name,
            file_data
        FROM assignment_submissions
        WHERE id = %s
    """, (submission_id,))

    submission = cursor.fetchone()

    cursor.close()
    db.close()

    if not submission:
        return "Submission not found.", 404

    return send_file(
        io.BytesIO(submission["file_data"]),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=submission["file_name"]
    )
    
@app.route("/assignment-submission-feedback/<int:submission_id>", methods=["POST"])
def assignment_submission_feedback(submission_id):

    if "user_id" not in session:
        return redirect("/")

    status = request.form["status"]
    feedback = request.form["feedback"].strip()

    allowed_status = [
        "Accepted",
        "Needs Correction",
        "Rejected"
    ]

    if status not in allowed_status:
        return "Invalid status.", 400

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE assignment_submissions
        SET status = %s,
            feedback = %s
        WHERE id = %s
    """, (
        status,
        feedback,
        submission_id
    ))

    db.commit()

    cursor.close()
    db.close()

    return redirect("/assignment-submissions")

@app.route("/student-attendance")
def student_attendance():

    if "student_id" not in session:
        return redirect("/student-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            attendance.id,
            attendance.subject,
            attendance.total_classes,
            attendance.attended_classes,
            attendance.attendance_percentage
        FROM attendance
        WHERE attendance.student_id = %s
        ORDER BY attendance.subject
    """, (session["student_id"],))

    attendance_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_attendance.html",
        attendance=attendance_data
    )
    
@app.route("/student-activities")
def student_activities():

    if "student_id" not in session:
        return redirect("/student-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            activities.id,
            activities.activity_name,
            activities.activity_type,
            activities.performance,
            activities.remarks
        FROM activities
        WHERE activities.student_id = %s
        ORDER BY activities.id DESC
    """, (session["student_id"],))

    activity_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_activities.html",
        activities=activity_data
    )
    
@app.route("/student-participation")
def student_participation():

    if "student_id" not in session:
        return redirect("/student-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            participation.id,
            participation.event_name,
            participation.event_type,
            participation.participation_level,
            participation.achievement,
            participation.remarks
        FROM participation
        WHERE participation.student_id = %s
        ORDER BY participation.id DESC
    """, (session["student_id"],))

    participation_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_participation.html",
        participation=participation_data
    )
    
@app.route("/student-overall-performance")
def student_overall_performance():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Theory
    cursor.execute("""
        SELECT
            SUM(marks) AS total_marks,
            SUM(max_marks) AS max_marks
        FROM marks
        WHERE student_id = %s
    """, (student_id,))

    theory = cursor.fetchone()

    # Practical
    cursor.execute("""
        SELECT
            SUM(marks) AS total_marks,
            SUM(max_marks) AS max_marks
        FROM practical
        WHERE student_id = %s
    """, (student_id,))

    practical = cursor.fetchone()

    # Assignment
    cursor.execute("""
        SELECT
            SUM(marks) AS total_marks,
            SUM(max_marks) AS max_marks
        FROM assignments
        WHERE student_id = %s
    """, (student_id,))

    assignment = cursor.fetchone()

    # Attendance
    cursor.execute("""
        SELECT AVG(attendance_percentage) AS attendance_percentage
        FROM attendance
        WHERE student_id = %s
    """, (student_id,))

    attendance = cursor.fetchone()

    cursor.close()
    db.close()

    # Calculate percentages

    theory_percentage = 0
    practical_percentage = 0
    assignment_percentage = 0
    attendance_percentage = 0

    if theory["max_marks"]:
        theory_percentage = (
            float(theory["total_marks"])
            / float(theory["max_marks"])
        ) * 100

    if practical["max_marks"]:
        practical_percentage = (
            float(practical["total_marks"])
            / float(practical["max_marks"])
        ) * 100

    if assignment["max_marks"]:
        assignment_percentage = (
            float(assignment["total_marks"])
            / float(assignment["max_marks"])
        ) * 100

    if attendance["attendance_percentage"] is not None:
        attendance_percentage = float(
            attendance["attendance_percentage"]
        )

    components = [
        theory_percentage,
        practical_percentage,
        assignment_percentage,
        attendance_percentage
    ]

    available_components = [
        value for value in components
        if value > 0
    ]

    if available_components:
        overall_percentage = (
            sum(available_components)
            / len(available_components)
        )
    else:
        overall_percentage = 0

    # Grade

    if overall_percentage >= 90:
        grade = "A+"
    elif overall_percentage >= 80:
        grade = "A"
    elif overall_percentage >= 70:
        grade = "B"
    elif overall_percentage >= 60:
        grade = "C"
    elif overall_percentage >= 50:
        grade = "D"
    else:
        grade = "F"

    # Performance Status

    if overall_percentage >= 75:
        performance_status = "Good Performance"
    elif overall_percentage >= 50:
        performance_status = "Average Performance"
    else:
        performance_status = "Needs Improvement"

    # Weak Area

    performance_components = {
        "Theory": theory_percentage,
        "Practical": practical_percentage,
        "Assignment": assignment_percentage,
        "Attendance": attendance_percentage
    }

    available_components = {
        name: value
        for name, value in performance_components.items()
        if value > 0
    }

    if available_components:
        weak_area = min(
            available_components,
            key=available_components.get
        )
    else:
        weak_area = "N/A"

    # Improvement message

    if weak_area == "Theory":
        improvement_message = (
            "Focus more on theory subjects and regular revision."
        )

    elif weak_area == "Practical":
        improvement_message = (
            "Practice more practical exercises and lab work."
        )

    elif weak_area == "Assignment":
        improvement_message = (
            "Complete assignments regularly and improve submission quality."
        )

    elif weak_area == "Attendance":
        improvement_message = (
            "Improve class attendance and maintain regular participation."
        )

    else:
        improvement_message = (
            "Keep maintaining your academic performance."
        )

    return render_template(
        "student_overall_performance.html",
        theory_percentage=round(theory_percentage, 2),
        practical_percentage=round(practical_percentage, 2),
        assignment_percentage=round(assignment_percentage, 2),
        attendance_percentage=round(attendance_percentage, 2),
        overall_percentage=round(overall_percentage, 2),
        grade=grade,
        performance_status=performance_status,
        weak_area=weak_area,
        improvement_message=improvement_message
    )

@app.route("/student-report")
def student_report():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Student Details
    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name,
            course,
            semester,
            email,
            phone
        FROM students
        WHERE id = %s
    """, (student_id,))

    student = cursor.fetchone()

    # Theory Marks
    cursor.execute("""
        SELECT
            subject,
            marks,
            max_marks
        FROM marks
        WHERE student_id = %s
        ORDER BY subject
    """, (student_id,))

    marks_data = cursor.fetchall()

    # Practical
    cursor.execute("""
        SELECT
            subject,
            marks,
            max_marks
        FROM practical
        WHERE student_id = %s
        ORDER BY subject
    """, (student_id,))

    practical_data = cursor.fetchall()

    # Assignments
    cursor.execute("""
        SELECT
            title,
            subject,
            marks,
            max_marks,
            submission_status
        FROM assignments
        WHERE student_id = %s
        ORDER BY id DESC
    """, (student_id,))

    assignment_data = cursor.fetchall()

    # Attendance
    cursor.execute("""
        SELECT
            subject,
            total_classes,
            attended_classes,
            attendance_percentage
        FROM attendance
        WHERE student_id = %s
        ORDER BY subject
    """, (student_id,))

    attendance_data = cursor.fetchall()

    # Activities
    cursor.execute("""
        SELECT
            activity_name,
            activity_type,
            performance,
            remarks
        FROM activities
        WHERE student_id = %s
        ORDER BY id DESC
    """, (student_id,))

    activity_data = cursor.fetchall()

    # Participation
    cursor.execute("""
        SELECT
            event_name,
            event_type,
            participation_level,
            achievement,
            remarks
        FROM participation
        WHERE student_id = %s
        ORDER BY id DESC
    """, (student_id,))

    participation_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_report.html",
        student=student,
        marks=marks_data,
        practical=practical_data,
        assignments=assignment_data,
        attendance=attendance_data,
        activities=activity_data,
        participation=participation_data
    )

@app.route("/student-download-report")
def student_download_report():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Student Details
    cursor.execute("""
        SELECT
            student_name,
            roll_no,
            course,
            semester,
            email,
            phone
        FROM students
        WHERE id = %s
    """, (student_id,))

    student = cursor.fetchone()

    # Theory
    cursor.execute("""
        SELECT subject, marks, max_marks
        FROM marks
        WHERE student_id = %s
        ORDER BY subject
    """, (student_id,))

    marks_data = cursor.fetchall()

    # Practical
    cursor.execute("""
        SELECT subject, marks, max_marks
        FROM practical
        WHERE student_id = %s
        ORDER BY subject
    """, (student_id,))

    practical_data = cursor.fetchall()

    # Assignments
    cursor.execute("""
        SELECT title, subject, marks, max_marks, submission_status
        FROM assignments
        WHERE student_id = %s
        ORDER BY id DESC
    """, (student_id,))

    assignment_data = cursor.fetchall()

    # Attendance
    cursor.execute("""
        SELECT subject, total_classes, attended_classes,
               attendance_percentage
        FROM attendance
        WHERE student_id = %s
        ORDER BY subject
    """, (student_id,))

    attendance_data = cursor.fetchall()

    cursor.close()
    db.close()

    # PDF
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER

    story = []

    story.append(
        Paragraph(
            "STUDENT PERFORMANCE REPORT",
            title_style
        )
    )

    story.append(Spacer(1, 20))

    # Student Information
    student_info = [
        ["Student Name", student["student_name"]],
        ["Roll Number", student["roll_no"]],
        ["Course", student["course"]],
        ["Semester", student["semester"]],
        ["Email", student["email"]],
        ["Phone", student["phone"]]
    ]

    table = Table(
        student_info,
        colWidths=[140, 350]
    )

    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 7)
        ])
    )

    story.append(table)

    story.append(Spacer(1, 20))

    # Theory Marks
    story.append(
        Paragraph(
            "Theory Marks",
            styles["Heading2"]
        )
    )

    theory_table = [
        ["Subject", "Obtained", "Maximum", "Percentage"]
    ]

    for item in marks_data:

        percentage = 0

        if item["max_marks"]:
            percentage = (
                float(item["marks"])
                / float(item["max_marks"])
            ) * 100

        theory_table.append([
            item["subject"],
            item["marks"],
            item["max_marks"],
            f"{percentage:.2f}%"
        ])

    if len(theory_table) == 1:
        theory_table.append(
            ["No records", "-", "-", "-"]
        )

    table = Table(
        theory_table,
        colWidths=[180, 100, 100, 110]
    )

    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 6)
        ])
    )

    story.append(table)

    story.append(Spacer(1, 20))

    # Practical
    story.append(
        Paragraph(
            "Practical Performance",
            styles["Heading2"]
        )
    )

    practical_table = [
        ["Subject", "Obtained", "Maximum", "Percentage"]
    ]

    for item in practical_data:

        percentage = 0

        if item["max_marks"]:
            percentage = (
                float(item["marks"])
                / float(item["max_marks"])
            ) * 100

        practical_table.append([
            item["subject"],
            item["marks"],
            item["max_marks"],
            f"{percentage:.2f}%"
        ])

    if len(practical_table) == 1:
        practical_table.append(
            ["No records", "-", "-", "-"]
        )

    table = Table(
        practical_table,
        colWidths=[180, 100, 100, 110]
    )

    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 6)
        ])
    )

    story.append(table)

    story.append(Spacer(1, 20))

    # Assignments
    story.append(
        Paragraph(
            "Assignments",
            styles["Heading2"]
        )
    )

    assignment_table = [
        ["Title", "Subject", "Marks", "Maximum", "Status"]
    ]

    for item in assignment_data:

        assignment_table.append([
            item["title"],
            item["subject"],
            item["marks"],
            item["max_marks"],
            item["submission_status"]
        ])

    if len(assignment_table) == 1:
        assignment_table.append(
            ["No records", "-", "-", "-", "-"]
        )

    table = Table(
        assignment_table,
        colWidths=[130, 110, 70, 70, 100]
    )

    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 1), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 5)
        ])
    )

    story.append(table)

    story.append(Spacer(1, 20))

    # Attendance
    story.append(
        Paragraph(
            "Attendance",
            styles["Heading2"]
        )
    )

    attendance_table = [
        [
            "Subject",
            "Total Classes",
            "Attended",
            "Attendance"
        ]
    ]

    for item in attendance_data:

        attendance_table.append([
            item["subject"],
            item["total_classes"],
            item["attended_classes"],
            f"{float(item['attendance_percentage']):.2f}%"
        ])

    if len(attendance_table) == 1:
        attendance_table.append(
            ["No records", "-", "-", "-"]
        )

    table = Table(
        attendance_table,
        colWidths=[180, 110, 100, 100]
    )

    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 6)
        ])
    )

    story.append(table)

    story.append(Spacer(1, 25))

    story.append(
        Paragraph(
            "Generated by Student Performance Analysis and Management System",
            styles["Normal"]
        )
    )

    doc.build(story)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Student_Performance_Report.pdf",
        mimetype="application/pdf"
    )
    
@app.route("/download-excel/<int:student_id>")
def download_excel(student_id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            students.roll_no,
            students.student_name,
            marks.subject,
            marks.marks,
            marks.max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        WHERE students.id = %s
        ORDER BY marks.subject
    """, (student_id,))

    report_data = cursor.fetchall()

    cursor.close()
    db.close()

    if not report_data:
        return "No marks found for this student."

    total_marks = sum(row["marks"] for row in report_data)
    max_marks = sum(row["max_marks"] for row in report_data)

    percentage = 0

    if max_marks > 0:
        percentage = (total_marks / max_marks) * 100

    if percentage >= 90:
        grade = "A+"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 70:
        grade = "B"
    elif percentage >= 60:
        grade = "C"
    elif percentage >= 50:
        grade = "D"
    else:
        grade = "F"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Student Report"

    sheet["A1"] = "STUDENT PERFORMANCE REPORT"
    sheet["A1"].font = Font(bold=True, size=16)

    sheet.merge_cells("A1:D1")
    sheet["A1"].alignment = Alignment(horizontal="center")

    sheet["A3"] = "Student Name"
    sheet["B3"] = report_data[0]["student_name"]

    sheet["A4"] = "Roll Number"
    sheet["B4"] = report_data[0]["roll_no"]

    sheet["A6"] = "Subject"
    sheet["B6"] = "Marks Obtained"
    sheet["C6"] = "Maximum Marks"
    sheet["D6"] = "Percentage"

    for cell in sheet[6]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    row_number = 7

    for row in report_data:

        sheet.cell(row=row_number, column=1, value=row["subject"])
        sheet.cell(row=row_number, column=2, value=row["marks"])
        sheet.cell(row=row_number, column=3, value=row["max_marks"])

        subject_percentage = 0

        if row["max_marks"] > 0:
            subject_percentage = (
                row["marks"] / row["max_marks"]
            ) * 100

        sheet.cell(
            row=row_number,
            column=4,
            value=round(subject_percentage, 2)
        )

        row_number += 1

    summary_row = row_number + 1

    sheet.cell(
        row=summary_row,
        column=1,
        value="Total Marks"
    )

    sheet.cell(
        row=summary_row,
        column=2,
        value=total_marks
    )

    sheet.cell(
        row=summary_row,
        column=3,
        value=max_marks
    )

    sheet.cell(
        row=summary_row + 1,
        column=1,
        value="Overall Percentage"
    )

    sheet.cell(
        row=summary_row + 1,
        column=2,
        value=round(percentage, 2)
    )

    sheet.cell(
        row=summary_row + 2,
        column=1,
        value="Grade"
    )

    sheet.cell(
        row=summary_row + 2,
        column=2,
        value=grade
    )

    for row in range(summary_row, summary_row + 3):
        sheet.cell(row=row, column=1).font = Font(bold=True)

    sheet.column_dimensions["A"].width = 25
    sheet.column_dimensions["B"].width = 20
    sheet.column_dimensions["C"].width = 20
    sheet.column_dimensions["D"].width = 18

    excel_buffer = io.BytesIO()

    workbook.save(excel_buffer)
    excel_buffer.seek(0)

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=f"{report_data[0]['student_name']}_Report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/student-logout")
def student_logout():

    session.pop("student_user_id", None)
    session.pop("student_id", None)
    session.pop("student_username", None)
    session.pop("student_name", None)
    session.pop("student_roll_no", None)

    return redirect("/student-login")


@app.route("/student-change-password", methods=["GET", "POST"])
def student_change_password():

    if "student_id" not in session:
        return redirect("/student-login")

    message = None
    error = None

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT password
            FROM student_users
            WHERE id = %s
        """, (session["student_user_id"],))

        student_user = cursor.fetchone()

        if not student_user:
            cursor.close()
            db.close()
            return redirect("/student-login")

        # Check current password
        if not check_password_hash(
            student_user["password"],
            current_password
        ):
            error = "Current password is incorrect."

        # Check new password
        elif new_password != confirm_password:
            error = "New password and confirm password do not match."

        elif len(new_password) < 6:
            error = "New password must be at least 6 characters."

        else:

            hashed_password = generate_password_hash(
                new_password
            )

            cursor.execute("""
                UPDATE student_users
                SET password = %s
                WHERE id = %s
            """, (
                hashed_password,
                session["student_user_id"]
            ))

            db.commit()

            message = "Password changed successfully."

        cursor.close()
        db.close()

    return render_template(
        "student_change_password.html",
        message=message,
        error=error
    )

@app.route("/student-accounts", methods=["GET", "POST"])
def student_accounts():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    message = None
    error = None

    if request.method == "POST":

        student_id = request.form["student_id"]
        username = request.form["username"]
        password = request.form["password"]

        # Check username already exists
        cursor.execute("""
            SELECT id
            FROM student_users
            WHERE username = %s
        """, (username,))

        existing_user = cursor.fetchone()

        if existing_user:
            error = "Username already exists."

        else:

            hashed_password = generate_password_hash(password)

            cursor.execute("""
                INSERT INTO student_users
                (student_id, username, password)
                VALUES (%s, %s, %s)
            """, (
                student_id,
                username,
                hashed_password
            ))

            db.commit()

            message = "Student account created successfully."

    # Get all students
    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    # Get existing student accounts
    cursor.execute("""
        SELECT
            student_users.id,
            student_users.username,
            students.student_name,
            students.roll_no
        FROM student_users
        JOIN students
        ON student_users.student_id = students.id
        ORDER BY students.student_name
    """)

    accounts = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_accounts.html",
        students=students_data,
        accounts=accounts,
        message=message,
        error=error
    )

@app.route("/reset-student-password/<int:account_id>", methods=["GET", "POST"])
def reset_student_password(account_id):

    if "user_id" not in session:
        return redirect("/")

    message = None
    error = None

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Student account details
    cursor.execute("""
        SELECT
            student_users.id,
            student_users.username,
            students.student_name,
            students.roll_no
        FROM student_users
        JOIN students
        ON student_users.student_id = students.id
        WHERE student_users.id = %s
    """, (account_id,))

    account = cursor.fetchone()

    if not account:
        cursor.close()
        db.close()
        return "Student account not found"

    if request.method == "POST":

        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if len(new_password) < 6:
            error = "Password must be at least 6 characters."

        elif new_password != confirm_password:
            error = "Passwords do not match."

        else:

            hashed_password = generate_password_hash(
                new_password
            )

            cursor.execute("""
                UPDATE student_users
                SET password = %s
                WHERE id = %s
            """, (
                hashed_password,
                account_id
            ))

            db.commit()

            message = "Student password reset successfully."

    cursor.close()
    db.close()

    return render_template(
        "reset_student_password.html",
        account=account,
        message=message,
        error=error
    )

@app.route("/change-student-username/<int:account_id>", methods=["GET", "POST"])
def change_student_username(account_id):

    if "user_id" not in session:
        return redirect("/")

    message = None
    error = None

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Student account details
    cursor.execute("""
        SELECT
            student_users.id,
            student_users.username,
            students.student_name,
            students.roll_no
        FROM student_users
        JOIN students
        ON student_users.student_id = students.id
        WHERE student_users.id = %s
    """, (account_id,))

    account = cursor.fetchone()

    if not account:
        cursor.close()
        db.close()
        return "Student account not found"

    if request.method == "POST":

        new_username = request.form["new_username"].strip()

        if len(new_username) < 4:
            error = "Username must be at least 4 characters."

        else:

            # Check username already exists
            cursor.execute("""
                SELECT id
                FROM student_users
                WHERE username = %s
                AND id != %s
            """, (new_username, account_id))

            existing_user = cursor.fetchone()

            if existing_user:
                error = "This username already exists."

            else:

                cursor.execute("""
                    UPDATE student_users
                    SET username = %s
                    WHERE id = %s
                """, (
                    new_username,
                    account_id
                ))

                db.commit()

                message = "Student username changed successfully."

                # Update displayed account information
                account["username"] = new_username

    cursor.close()
    db.close()

    return render_template(
        "change_student_username.html",
        account=account,
        message=message,
        error=error
    )

@app.route("/send-message", methods=["GET", "POST"])
def send_message():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    message = None
    error = None

    if request.method == "POST":

        student_id = request.form["student_id"]
        title = request.form["title"].strip()
        msg = request.form["message"].strip()

        if not student_id:
            error = "Please select a student."

        elif not title:
            error = "Please enter message title."

        elif not msg:
            error = "Please enter message."

        else:

            cursor.execute("""
                INSERT INTO student_messages
                (student_id, title, message)
                VALUES (%s, %s, %s)
            """, (
                student_id,
                title,
                msg
            ))

            db.commit()

            message = "Message sent successfully."

    cursor.execute("""
        SELECT id, student_name, roll_no
        FROM students
        ORDER BY student_name
    """)

    students = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "send_message.html",
        students=students,
        message=message,
        error=error
    )
    


    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            title,
            message,
            created_at,
            is_read
        FROM student_messages
        WHERE student_id = %s
        ORDER BY created_at DESC
    """, (student_id,))

    messages = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_messages.html",
        messages=messages
    )

@app.route("/student-messages")
def student_messages():

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # GET ALL MESSAGES
    # =========================

    cursor.execute("""
        SELECT
            id,
            title,
            message,
            created_at,
            is_read
        FROM student_messages
        WHERE student_id = %s
        ORDER BY created_at DESC
    """, (student_id,))

    messages = cursor.fetchall()


    # =========================
    # GET UNREAD COUNT
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS unread_count
        FROM student_messages
        WHERE student_id = %s
        AND is_read = FALSE
    """, (student_id,))

    result = cursor.fetchone()

    unread_count = result["unread_count"]


    # =========================
    # CLOSE DATABASE
    # =========================

    cursor.close()
    db.close()


    return render_template(
        "student_messages.html",
        messages=messages,
        unread_count=unread_count
    )


@app.route("/student-message/<int:message_id>")
def view_student_message(message_id):

    if "student_id" not in session:
        return redirect("/student-login")

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # GET MESSAGE
    # =========================

    cursor.execute("""
        SELECT
            id,
            title,
            message,
            created_at,
            is_read
        FROM student_messages
        WHERE id = %s
        AND student_id = %s
    """, (message_id, student_id))

    msg = cursor.fetchone()


    if not msg:

        cursor.close()
        db.close()

        return "Message not found"


    # =========================
    # MARK MESSAGE AS READ
    # =========================

    cursor.execute("""
        UPDATE student_messages
        SET is_read = TRUE
        WHERE id = %s
        AND student_id = %s
    """, (message_id, student_id))

    db.commit()


    cursor.close()
    db.close()


    return render_template(
        "view_student_message.html",
        msg=msg
    )

@app.route("/delete-student-account/<int:account_id>")
def delete_student_account(account_id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM student_users
        WHERE id = %s
    """, (account_id,))

    db.commit()

    cursor.close()
    db.close()

    return redirect("/student-accounts")

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # TOTAL STUDENTS
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS total_students
        FROM students
    """)

    total_students = cursor.fetchone()["total_students"]

   # =========================
    # RECENT STUDENTS
    # =========================

    cursor.execute("""
    SELECT
        id,
        roll_no,
        student_name,
        course,
        semester
    FROM students
    ORDER BY id DESC
    LIMIT 5
""")
    
    
    recent_students = cursor.fetchall()
    print("RECENT STUDENTS:", recent_students)
    
    # =========================
    # AVERAGE THEORY PERFORMANCE
    # =========================

    cursor.execute("""
                    SELECT
                    AVG(student_percentage) AS average_percentage
                    FROM (
                    SELECT
                    student_id,
                    (SUM(marks) / SUM(max_marks)) * 100 AS student_percentage
                    FROM marks
                    GROUP BY student_id
                    ) AS performance
                    """)
    result = cursor.fetchone()

    average_percentage = float(
    result["average_percentage"] or 0
)


    # =========================
    # AVERAGE ATTENDANCE
    # =========================

    cursor.execute("""
        SELECT
            AVG(attendance_percentage) AS average_attendance
        FROM attendance
    """)

    result = cursor.fetchone()

    average_attendance = result["average_attendance"] or 0


    # =========================
    # TOTAL THEORY RECORDS
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS total_reports
        FROM marks
    """)

    total_reports = cursor.fetchone()["total_reports"]


    # =========================
    # TOTAL PRACTICAL RECORDS
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS total_practical
        FROM practical
    """)

    total_practical = cursor.fetchone()["total_practical"]


    # =========================
    # TOTAL ASSIGNMENTS
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS total_assignments
        FROM assignments
    """)

    total_assignments = cursor.fetchone()["total_assignments"]


    # =========================
    # TOTAL ACTIVITIES
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS total_activities
        FROM activities
    """)

    total_activities = cursor.fetchone()["total_activities"]


    # =========================
    # TOTAL PARTICIPATIONS
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS total_participations
        FROM participation
    """)

    total_participations = cursor.fetchone()["total_participations"]


    # =========================
    # LOW ATTENDANCE STUDENTS
    # =========================

    cursor.execute("""
        SELECT COUNT(*) AS low_attendance_students
        FROM (
            SELECT
                student_id,
                AVG(attendance_percentage) AS avg_attendance
            FROM attendance
            GROUP BY student_id
            HAVING AVG(attendance_percentage) < 75
        ) AS low_attendance
    """)

    result = cursor.fetchone()

    low_attendance_students = result["low_attendance_students"]


    # =========================
    # LOW ATTENDANCE STUDENT LIST
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            students.roll_no,
            AVG(attendance.attendance_percentage) AS avg_attendance
        FROM students
        JOIN attendance
        ON students.id = attendance.student_id
        GROUP BY
            students.id,
            students.student_name,
            students.roll_no
        HAVING AVG(attendance.attendance_percentage) < 75
        ORDER BY avg_attendance ASC
    """)

    low_attendance_list = cursor.fetchall()


    # =========================
    # TOP PERFORMER
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            students.roll_no,
            SUM(marks.marks) AS total_marks,
            SUM(marks.max_marks) AS max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        GROUP BY
            students.id,
            students.student_name,
            students.roll_no
        ORDER BY
            (SUM(marks.marks) / SUM(marks.max_marks)) DESC
        LIMIT 1
    """)

    top_performer = cursor.fetchone()

    if top_performer:

        top_performer_percentage = round(
            (
                top_performer["total_marks"]
                / top_performer["max_marks"]
            ) * 100,
            2
        )

        top_performer["percentage"] = top_performer_percentage

    else:

        top_performer_percentage = 0


    # =========================
    # NEEDS IMPROVEMENT
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            students.roll_no,
            SUM(marks.marks) AS total_marks,
            SUM(marks.max_marks) AS max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        GROUP BY
            students.id,
            students.student_name,
            students.roll_no
        ORDER BY
            (SUM(marks.marks) / SUM(marks.max_marks)) ASC
        LIMIT 1
    """)

    needs_improvement = cursor.fetchone()

    if needs_improvement:

        needs_improvement_percentage = round(
            (
                needs_improvement["total_marks"]
                / needs_improvement["max_marks"]
            ) * 100,
            2
        )

        needs_improvement["percentage"] = needs_improvement_percentage

    else:

        needs_improvement_percentage = 0


    # =========================
    # PERFORMANCE WARNING LIST
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            students.roll_no,
            SUM(marks.marks) AS total_marks,
            SUM(marks.max_marks) AS max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        GROUP BY
            students.id,
            students.student_name,
            students.roll_no
        ORDER BY
            (SUM(marks.marks) / SUM(marks.max_marks)) ASC
    """)

    performance_warning_data = cursor.fetchall()

    performance_warning_list = []

    for student in performance_warning_data:

        total_marks = float(student["total_marks"] or 0)
        max_marks = float(student["max_marks"] or 0)

        if max_marks > 0:
            percentage = (total_marks / max_marks) * 100
        else:
            percentage = 0

        if percentage < 50:
            status = "Critical"

        elif percentage < 60:
            status = "Needs Improvement"

        elif percentage < 75:
            status = "Average"

        else:
            status = "Good"

        performance_warning_list.append({
            "student_name": student["student_name"],
            "roll_no": student["roll_no"],
            "percentage": round(percentage, 2),
            "status": status
        })


    # =========================
    # PERFORMANCE CHART
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            SUM(marks.marks) AS total_marks,
            SUM(marks.max_marks) AS max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        GROUP BY
            students.id,
            students.student_name
        ORDER BY students.student_name
    """)

    performance_data = cursor.fetchall()

    performance_names = []
    performance_values = []

    for student in performance_data:

        performance_names.append(
            student["student_name"]
        )

        if student["max_marks"] > 0:

            percentage = (
                student["total_marks"]
                / student["max_marks"]
            ) * 100

        else:

            percentage = 0

        performance_values.append(
            round(percentage, 2)
        )


    # =========================
    # ATTENDANCE CHART
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            AVG(attendance.attendance_percentage)
            AS attendance_percentage
        FROM students
        JOIN attendance
        ON students.id = attendance.student_id
        GROUP BY
            students.id,
            students.student_name
        ORDER BY students.student_name
    """)

    attendance_data = cursor.fetchall()

    attendance_names = []
    attendance_values = []

    for student in attendance_data:

        attendance_names.append(
            student["student_name"]
        )

        attendance_values.append(
            round(
                float(
                    student["attendance_percentage"] or 0
                ),
                2
            )
        )


    # =========================
    # CLOSE DATABASE
    # =========================

    cursor.close()
    db.close()


    # =========================
    # SEND DATA TO TEMPLATE
    # =========================

    return render_template(
        "dashboard.html",

        total_students=total_students,

         recent_students=recent_students,

         average_percentage=average_percentage,

        average_attendance=average_attendance,

        total_reports=total_reports,

        total_practical=total_practical,

        total_assignments=total_assignments,

        total_activities=total_activities,

        total_participations=total_participations,

        low_attendance_students=low_attendance_students,

        low_attendance_list=low_attendance_list,

        performance_names=performance_names,

        performance_values=performance_values,

        attendance_names=attendance_names,

        attendance_values=attendance_values,

        top_performer=top_performer,

        top_performer_percentage=top_performer_percentage,

        needs_improvement=needs_improvement,

        needs_improvement_percentage=needs_improvement_percentage,

        performance_warning_list=performance_warning_list
)


# =========================
# ADD STUDENT
# =========================

@app.route("/add-student", methods=["GET", "POST"])
def add_student():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        roll_no = request.form["roll_no"]
        student_name = request.form["student_name"]
        course = request.form["course"]
        semester = request.form["semester"]
        email = request.form["email"]
        phone = request.form["phone"]

        db = get_db_connection()
        cursor = db.cursor()

        query = """
        INSERT INTO students
        (roll_no, student_name, course, semester, email, phone)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (
            roll_no,
            student_name,
            course,
            semester,
            email,
            phone
        )

        cursor.execute(query, values)
        db.commit()

        cursor.close()
        db.close()

        return redirect("/students")

    return render_template("add_student.html")

@app.route("/students")
def students():
    if "user_id" not in session:
        return redirect("/")

    search = request.args.get("search", "").strip()
    course = request.args.get("course", "").strip()
    semester = request.args.get("semester", "").strip()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT *
        FROM students
        WHERE 1=1
    """

    params = []

    # Search by name or roll number
    if search:
        query += """
            AND (
                student_name LIKE %s
                OR roll_no LIKE %s
            )
        """

        search_value = "%" + search + "%"
        params.extend([search_value, search_value])

    # Filter by course
    if course:
        query += " AND course = %s"
        params.append(course)

    # Filter by semester
    if semester:
        query += " AND semester = %s"
        params.append(semester)

    query += " ORDER BY id DESC"

    cursor.execute(query, tuple(params))
    student_data = cursor.fetchall()

    # Get courses for dropdown
    cursor.execute("""
        SELECT DISTINCT course
        FROM students
        WHERE course IS NOT NULL
          AND course != ''
        ORDER BY course
    """)

    courses = cursor.fetchall()

    # Get semesters for dropdown
    cursor.execute("""
        SELECT DISTINCT semester
        FROM students
        WHERE semester IS NOT NULL
          AND semester != ''
        ORDER BY semester
    """)

    semesters = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "students.html",
        students=student_data,
        search=search,
        course=course,
        semester=semester,
        courses=courses,
        semesters=semesters
    )
@app.route("/edit-student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if "user_id" not in session:
        return redirect("/")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        roll_no = request.form["roll_no"]
        student_name = request.form["student_name"]
        course = request.form["course"]
        semester = request.form["semester"]
        email = request.form["email"]
        phone = request.form["phone"]

        update_query = """
        UPDATE students
        SET roll_no = %s,
            student_name = %s,
            course = %s,
            semester = %s,
            email = %s,
            phone = %s
        WHERE id = %s
        """

        values = (
            roll_no,
            student_name,
            course,
            semester,
            email,
            phone,
            id
        )

        cursor.execute(update_query, values)
        db.commit()

        cursor.close()
        db.close()

        return redirect("/students")

    cursor.execute(
        "SELECT * FROM students WHERE id = %s",
        (id,)
    )

    student = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template(
        "edit_student.html",
        student=student
    )

# =========================
# ADD MARKS
# =========================

@app.route("/add-marks", methods=["GET", "POST"])
def add_marks():
    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        student_id = request.form["student_id"]
        subject = request.form["subject"]

        try:
            marks = float(request.form["marks"])
            max_marks = float(request.form["max_marks"])
        except ValueError:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_marks.html",
                students=students_data,
                error="Please enter valid numeric marks."
            )

        # =========================
        # MARKS VALIDATION
        # =========================

        if max_marks <= 0:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_marks.html",
                students=students_data,
                error="Maximum marks must be greater than 0."
            )

        if marks < 0:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_marks.html",
                students=students_data,
                error="Marks cannot be negative."
            )

        if marks > max_marks:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_marks.html",
                students=students_data,
                error="Marks cannot be greater than maximum marks."
            )

        # =========================
        # SAVE MARKS
        # =========================

        query = """
        INSERT INTO marks
        (student_id, subject, marks, max_marks)
        VALUES (%s, %s, %s, %s)
        """

        values = (
            student_id,
            subject,
            marks,
            max_marks
        )

        cursor.execute(query, values)
        db.commit()

        cursor.close()
        db.close()

        return redirect("/marks")

    # =========================
    # LOAD STUDENTS
    # =========================

    cursor.execute(
        "SELECT * FROM students ORDER BY student_name"
    )

    students_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_marks.html",
        students=students_data
    )

# =========================
# MARKS LIST
# =========================

@app.route("/marks")
def marks():
    if "user_id" not in session:
        return redirect("/")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
    SELECT marks.id,
           students.roll_no,
           students.student_name,
           marks.subject,
           marks.marks,
           marks.max_marks
    FROM marks
    JOIN students
    ON marks.student_id = students.id
    ORDER BY marks.id DESC
    """

    cursor.execute(query)

    marks_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "marks.html",
        marks=marks_data
    )

# =========================
# ADD ATTENDANCE
# =========================

@app.route("/add-attendance", methods=["GET", "POST"])
def add_attendance():
    
    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        student_id = request.form["student_id"]
        subject = request.form["subject"]

        try:
            total_classes = int(request.form["total_classes"])
            attended_classes = int(request.form["attended_classes"])
        except ValueError:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_attendance.html",
                students=students_data,
                error="Please enter valid class numbers."
            )

        # =========================
        # ATTENDANCE VALIDATION
        # =========================

        if total_classes <= 0:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_attendance.html",
                students=students_data,
                error="Total classes must be greater than 0."
            )

        if attended_classes < 0:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_attendance.html",
                students=students_data,
                error="Attended classes cannot be negative."
            )

        if attended_classes > total_classes:

            cursor.execute(
                "SELECT * FROM students ORDER BY student_name"
            )

            students_data = cursor.fetchall()

            cursor.close()
            db.close()

            return render_template(
                "add_attendance.html",
                students=students_data,
                error="Attended classes cannot be greater than total classes."
            )

        # =========================
        # CALCULATE ATTENDANCE
        # =========================

        attendance_percentage = (
            attended_classes / total_classes
        ) * 100

        # =========================
        # SAVE ATTENDANCE
        # =========================

        query = """
        INSERT INTO attendance
        (
            student_id,
            subject,
            total_classes,
            attended_classes,
            attendance_percentage
        )
        VALUES (%s, %s, %s, %s, %s)
        """

        values = (
            student_id,
            subject,
            total_classes,
            attended_classes,
            attendance_percentage
        )

        cursor.execute(query, values)
        db.commit()

        cursor.close()
        db.close()

        return redirect("/attendance")

    # =========================
    # LOAD STUDENTS
    # =========================

    cursor.execute(
        "SELECT * FROM students ORDER BY student_name"
    )

    students_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_attendance.html",
        students=students_data
    )
# =========================
# ADD PRACTICAL
# =========================

@app.route("/add-practical", methods=["GET", "POST"])
def add_practical():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        student_id = request.form["student_id"]
        subject = request.form["subject"]
        marks = request.form["marks"]
        max_marks = request.form["max_marks"]

        # =========================
        # VALIDATION
        # =========================

        try:
            marks = float(marks)
            max_marks = float(max_marks)

            if max_marks <= 0:
                return "Maximum marks must be greater than 0"

            if marks < 0:
                return "Marks cannot be negative"

            if marks > max_marks:
                return "Obtained marks cannot be greater than maximum marks"

        except ValueError:
            return "Please enter valid marks"

        # =========================
        # INSERT PRACTICAL
        # =========================

        cursor.execute("""
            INSERT INTO practical
            (student_id, subject, marks, max_marks)
            VALUES (%s, %s, %s, %s)
        """, (
            student_id,
            subject,
            marks,
            max_marks
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/practical")

    # =========================
    # GET STUDENTS
    # =========================

    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_practical.html",
        students=students_data
    )


# =========================
# PRACTICAL RECORDS
# =========================

@app.route("/practical")
def practical():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            practical.id,
            students.roll_no,
            students.student_name,
            practical.subject,
            practical.marks,
            practical.max_marks
        FROM practical
        JOIN students
        ON students.id = practical.student_id
        ORDER BY practical.id DESC
    """)

    practical_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "practical.html",
        practical=practical_data
    )


# =========================
# DELETE PRACTICAL
# =========================

@app.route("/delete-practical/<int:id>")
def delete_practical(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM practical WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/practical")


@app.route("/edit-practical/<int:id>", methods=["GET", "POST"])
def edit_practical(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        subject = request.form["subject"]
        marks = request.form["marks"]
        max_marks = request.form["max_marks"]

        try:
            marks = float(marks)
            max_marks = float(max_marks)

            if max_marks <= 0:
                return "Maximum marks must be greater than 0"

            if marks < 0:
                return "Marks cannot be negative"

            if marks > max_marks:
                return "Obtained marks cannot be greater than maximum marks"

        except ValueError:
            return "Please enter valid marks"

        cursor.execute("""
            UPDATE practical
            SET
                subject = %s,
                marks = %s,
                max_marks = %s
            WHERE id = %s
        """, (
            subject,
            marks,
            max_marks,
            id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/practical")

    cursor.execute("""
        SELECT
            practical.id,
            practical.subject,
            practical.marks,
            practical.max_marks,
            students.student_name,
            students.roll_no
        FROM practical
        JOIN students
        ON students.id = practical.student_id
        WHERE practical.id = %s
    """, (id,))

    record = cursor.fetchone()

    cursor.close()
    db.close()

    if not record:
        return "Practical record not found"

    return render_template(
        "edit_practical.html",
        practical=record
    )
# =========================
# ADD ASSIGNMENT
# =========================

@app.route("/add-assignment", methods=["GET", "POST"])
def add_assignment():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        student_id = request.form["student_id"]
        title = request.form["title"]
        subject = request.form["subject"]
        marks = request.form["marks"]
        max_marks = request.form["max_marks"]
        submission_status = request.form["submission_status"]

        # =========================
        # VALIDATION
        # =========================

        try:

            marks = float(marks)
            max_marks = float(max_marks)

            if max_marks <= 0:
                return "Maximum marks must be greater than 0"

            if marks < 0:
                return "Marks cannot be negative"

            if marks > max_marks:
                return "Obtained marks cannot be greater than maximum marks"

        except ValueError:

            return "Please enter valid marks"

        # =========================
        # INSERT ASSIGNMENT
        # =========================

        cursor.execute("""
            INSERT INTO assignments
            (
                student_id,
                title,
                subject,
                marks,
                max_marks,
                submission_status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            student_id,
            title,
            subject,
            marks,
            max_marks,
            submission_status
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/assignments")

    # =========================
    # GET STUDENTS
    # =========================

    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_assignment.html",
        students=students_data
    )


# =========================
# ASSIGNMENT RECORDS
# =========================

@app.route("/assignments")
def assignments():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            assignments.id,
            students.roll_no,
            students.student_name,
            assignments.title,
            assignments.subject,
            assignments.marks,
            assignments.max_marks,
            assignments.submission_status
        FROM assignments
        JOIN students
        ON students.id = assignments.student_id
        ORDER BY assignments.id DESC
    """)

    assignment_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "assignments.html",
        assignments=assignment_data
    )
    
# =========================
# EDIT ASSIGNMENT
# =========================

@app.route("/edit-assignment/<int:id>", methods=["GET", "POST"])
def edit_assignment(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        title = request.form["title"]
        subject = request.form["subject"]
        marks = request.form["marks"]
        max_marks = request.form["max_marks"]
        submission_status = request.form["submission_status"]

        try:
            marks = float(marks)
            max_marks = float(max_marks)

            if max_marks <= 0:
                return "Maximum marks must be greater than 0"

            if marks < 0:
                return "Marks cannot be negative"

            if marks > max_marks:
                return "Obtained marks cannot be greater than maximum marks"

        except ValueError:
            return "Please enter valid marks"

        cursor.execute("""
            UPDATE assignments
            SET
                title = %s,
                subject = %s,
                marks = %s,
                max_marks = %s,
                submission_status = %s
            WHERE id = %s
        """, (
            title,
            subject,
            marks,
            max_marks,
            submission_status,
            id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/assignments")

    cursor.execute("""
        SELECT
            assignments.id,
            assignments.title,
            assignments.subject,
            assignments.marks,
            assignments.max_marks,
            assignments.submission_status,
            students.student_name,
            students.roll_no
        FROM assignments
        JOIN students
        ON students.id = assignments.student_id
        WHERE assignments.id = %s
    """, (id,))

    record = cursor.fetchone()

    cursor.close()
    db.close()

    if not record:
        return "Assignment record not found"

    return render_template(
        "edit_assignment.html",
        assignment=record
    )


# =========================
# DELETE ASSIGNMENT
# =========================

@app.route("/delete-assignment/<int:id>")
def delete_assignment(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM assignments WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/assignments")
# =========================
# ADD ACTIVITY
# =========================

@app.route("/add-activity", methods=["GET", "POST"])
def add_activity():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        student_id = request.form["student_id"]
        activity_name = request.form["activity_name"]
        activity_type = request.form["activity_type"]
        performance = request.form["performance"]
        remarks = request.form["remarks"]

        # =========================
        # INSERT ACTIVITY
        # =========================

        cursor.execute("""
            INSERT INTO activities
            (
                student_id,
                activity_name,
                activity_type,
                performance,
                remarks
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            student_id,
            activity_name,
            activity_type,
            performance,
            remarks
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/activities")

    # =========================
    # GET STUDENTS
    # =========================

    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_activity.html",
        students=students_data
    )


# =========================
# ACTIVITY RECORDS
# =========================

@app.route("/activities")
def activities():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            activities.id,
            students.roll_no,
            students.student_name,
            activities.activity_name,
            activities.activity_type,
            activities.performance,
            activities.remarks
        FROM activities
        JOIN students
        ON students.id = activities.student_id
        ORDER BY activities.id DESC
    """)

    activity_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "activities.html",
        activities=activity_data
    )

# =========================
# EDIT ACTIVITY
# =========================

@app.route("/edit-activity/<int:id>", methods=["GET", "POST"])
def edit_activity(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        activity_name = request.form["activity_name"]
        activity_type = request.form["activity_type"]
        performance = request.form["performance"]
        remarks = request.form["remarks"]

        cursor.execute("""
            UPDATE activities
            SET
                activity_name = %s,
                activity_type = %s,
                performance = %s,
                remarks = %s
            WHERE id = %s
        """, (
            activity_name,
            activity_type,
            performance,
            remarks,
            id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/activities")

    cursor.execute("""
        SELECT
            activities.id,
            activities.activity_name,
            activities.activity_type,
            activities.performance,
            activities.remarks,
            students.student_name,
            students.roll_no
        FROM activities
        JOIN students
        ON students.id = activities.student_id
        WHERE activities.id = %s
    """, (id,))

    record = cursor.fetchone()

    cursor.close()
    db.close()

    if not record:
        return "Activity record not found"

    return render_template(
        "edit_activity.html",
        activity=record
    )


# =========================
# DELETE ACTIVITY
# =========================

@app.route("/delete-activity/<int:id>")
def delete_activity(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM activities WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/activities")
# =========================
# ADD PARTICIPATION
# =========================

@app.route("/add-participation", methods=["GET", "POST"])
def add_participation():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        student_id = request.form["student_id"]
        event_name = request.form["event_name"]
        event_type = request.form["event_type"]
        participation_level = request.form["participation_level"]
        achievement = request.form["achievement"]
        remarks = request.form["remarks"]

        # =========================
        # INSERT PARTICIPATION
        # =========================

        cursor.execute("""
            INSERT INTO participation
            (
                student_id,
                event_name,
                event_type,
                participation_level,
                achievement,
                remarks
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            student_id,
            event_name,
            event_type,
            participation_level,
            achievement,
            remarks
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/participation")

    # =========================
    # GET STUDENTS
    # =========================

    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_participation.html",
        students=students_data
    )


# =========================
# PARTICIPATION RECORDS
# =========================

@app.route("/participation")
def participation():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            participation.id,
            students.roll_no,
            students.student_name,
            participation.event_name,
            participation.event_type,
            participation.participation_level,
            participation.achievement,
            participation.remarks
        FROM participation
        JOIN students
        ON students.id = participation.student_id
        ORDER BY participation.id DESC
    """)

    participation_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "participation.html",
        participation=participation_data
    )
# =========================
# EDIT PARTICIPATION
# =========================

@app.route("/edit-participation/<int:id>", methods=["GET", "POST"])
def edit_participation(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        event_name = request.form["event_name"]
        event_type = request.form["event_type"]
        participation_level = request.form["participation_level"]
        achievement = request.form["achievement"]
        remarks = request.form["remarks"]

        cursor.execute("""
            UPDATE participation
            SET
                event_name = %s,
                event_type = %s,
                participation_level = %s,
                achievement = %s,
                remarks = %s
            WHERE id = %s
        """, (
            event_name,
            event_type,
            participation_level,
            achievement,
            remarks,
            id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/participation")

    cursor.execute("""
        SELECT
            participation.id,
            participation.event_name,
            participation.event_type,
            participation.participation_level,
            participation.achievement,
            participation.remarks,
            students.student_name,
            students.roll_no
        FROM participation
        JOIN students
        ON students.id = participation.student_id
        WHERE participation.id = %s
    """, (id,))

    record = cursor.fetchone()

    cursor.close()
    db.close()

    if not record:
        return "Participation record not found"

    return render_template(
        "edit_participation.html",
        participation=record
    )


# =========================
# DELETE PARTICIPATION
# =========================

@app.route("/delete-participation/<int:id>")
def delete_participation(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM participation WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/participation")

@app.route("/attendance")
def attendance():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            attendance.id,
            students.roll_no,
            students.student_name,
            attendance.subject,
            attendance.total_classes,
            attendance.attended_classes,
            attendance.attendance_percentage
        FROM attendance
        JOIN students
        ON students.id = attendance.student_id
        ORDER BY students.student_name, attendance.subject
    """)

    attendance_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "attendance.html",
        attendance=attendance_data
    )
# =========================
# EDIT ATTENDANCE
# =========================

@app.route("/edit-attendance/<int:id>", methods=["GET", "POST"])
def edit_attendance(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        subject = request.form["subject"]
        total_classes = request.form["total_classes"]
        attended_classes = request.form["attended_classes"]

        try:
            total_classes = int(total_classes)
            attended_classes = int(attended_classes)

            if total_classes <= 0:
                return "Total classes must be greater than 0"

            if attended_classes < 0:
                return "Attended classes cannot be negative"

            if attended_classes > total_classes:
                return "Attended classes cannot be greater than total classes"

        except ValueError:
            return "Please enter valid class numbers"

        attendance_percentage = (
            attended_classes / total_classes
        ) * 100

        cursor.execute("""
            UPDATE attendance
            SET
                subject = %s,
                total_classes = %s,
                attended_classes = %s,
                attendance_percentage = %s
            WHERE id = %s
        """, (
            subject,
            total_classes,
            attended_classes,
            attendance_percentage,
            id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/attendance")

    cursor.execute("""
        SELECT
            attendance.id,
            attendance.subject,
            attendance.total_classes,
            attendance.attended_classes,
            attendance.attendance_percentage,
            students.student_name,
            students.roll_no
        FROM attendance
        JOIN students
        ON students.id = attendance.student_id
        WHERE attendance.id = %s
    """, (id,))

    record = cursor.fetchone()

    cursor.close()
    db.close()

    if not record:
        return "Attendance record not found"

    return render_template(
        "edit_attendance.html",
        attendance=record
    )
    # =========================
# DELETE ATTENDANCE
# =========================

@app.route("/delete-attendance/<int:id>")
def delete_attendance(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM attendance WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/attendance")

# =========================
# ATTENDANCE LIST
# =========================
@app.route("/performance")
def performance():
    if "user_id" not in session:
        return redirect("/")
    # Search value
    search = request.args.get("search", "").strip()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # OVERALL PERFORMANCE
    # =========================

    if search:

        query = """
        SELECT
            students.roll_no,
            students.student_name,
            SUM(marks.marks) AS total_marks,
            SUM(marks.max_marks) AS max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        WHERE students.student_name LIKE %s
           OR students.roll_no LIKE %s
        GROUP BY students.id,
                 students.roll_no,
                 students.student_name
        ORDER BY students.student_name
        """

        search_value = "%" + search + "%"

        cursor.execute(
            query,
            (search_value, search_value)
        )

    else:

        cursor.execute("""
            SELECT
                students.roll_no,
                students.student_name,
                SUM(marks.marks) AS total_marks,
                SUM(marks.max_marks) AS max_marks
            FROM students
            JOIN marks
            ON students.id = marks.student_id
            GROUP BY students.id,
                     students.roll_no,
                     students.student_name
            ORDER BY students.student_name
        """)

    performance_data = cursor.fetchall()


    # =========================
    # PERCENTAGE + GRADE
    # =========================

    for student in performance_data:

        if student["max_marks"] > 0:

            student["percentage"] = (
                student["total_marks"] /
                student["max_marks"]
            ) * 100

        else:

            student["percentage"] = 0


        percentage = student["percentage"]


        if percentage >= 90:
            student["grade"] = "A+"

        elif percentage >= 80:
            student["grade"] = "A"

        elif percentage >= 70:
            student["grade"] = "B"

        elif percentage >= 60:
            student["grade"] = "C"

        elif percentage >= 50:
            student["grade"] = "D"

        else:
            student["grade"] = "F"


    # =========================
    # TOP PERFORMER
    # =========================

    top_performer = None

    if performance_data:

        top_performer = max(
            performance_data,
            key=lambda student: student["percentage"]
        )
        needs_improvement = cursor.fetchone()
        if needs_improvement:
            needs_improvement_percentage = round(
        (
            needs_improvement["total_marks"]
            / needs_improvement["max_marks"]
        ) * 100,
        2
    )
            needs_improvement["percentage"] = needs_improvement_percentage
        else:
            needs_improvement_percentage = 0
            
            # PERFORMANCE WARNING LIST
            cursor.execute("""
                           SELECT
                           students.student_name,
                           students.roll_no,
                           SUM(marks.marks) AS total_marks,
                           SUM(marks.max_marks) AS max_marks
                           FROM students
                           JOIN marks
                           ON students.id = marks.student_id
                           GROUP BY
                           students.id,
                           students.student_name,
                           students.roll_no
                           ORDER BY
                           (SUM(marks.marks) / SUM(marks.max_marks)) ASC
                           """)
            performance_warning_data = cursor.fetchall()

            performance_warning_list = []

            for student in performance_warning_data:
                total_marks = float(student["total_marks"] or 0)
                max_marks = float(student["max_marks"] or 0)
                if max_marks > 0:
                    percentage = (total_marks / max_marks) * 100
    else:
        percentage = 0

    if percentage < 50:
        status = "Critical"
    elif percentage < 60:
        status = "Needs Improvement"
    elif percentage < 75:
        status = "Average"
    else:
        status = "Good"

    performance_warning_list.append({
        "student_name": student["student_name"],
        "roll_no": student["roll_no"],
        "percentage": round(percentage, 2),
        "status": status
    })
    
    
# =========================
# =========================
# STUDENT REPORT
# =========================

@app.route("/report")
def report():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Get all students
    cursor.execute("""
        SELECT
            id,
            roll_no,
            student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    selected_student_id = request.args.get("student_id")

    report_data = []

    total_marks = 0
    max_marks = 0
    percentage = 0
    grade = "-"
    selected_student = None

    # If student is selected
    if selected_student_id:

        cursor.execute("""
            SELECT
                students.id,
                students.roll_no,
                students.student_name,
                marks.subject,
                marks.marks,
                marks.max_marks
            FROM students
            JOIN marks
            ON students.id = marks.student_id
            WHERE students.id = %s
            ORDER BY marks.subject
        """, (selected_student_id,))

        report_data = cursor.fetchall()

        if report_data:

            selected_student = report_data[0]

            total_marks = sum(
                record["marks"]
                for record in report_data
            )

            max_marks = sum(
                record["max_marks"]
                for record in report_data
            )

            if max_marks > 0:

                percentage = (
                    total_marks /
                    max_marks
                ) * 100

            # Grade
            if percentage >= 90:
                grade = "A+"

            elif percentage >= 80:
                grade = "A"

            elif percentage >= 70:
                grade = "B"

            elif percentage >= 60:
                grade = "C"

            elif percentage >= 50:
                grade = "D"

            else:
                grade = "F"

    cursor.close()
    db.close()

    return render_template(
        "report.html",
        students=students_data,
        report=report_data,
        selected_student_id=selected_student_id,
        selected_student=selected_student,
        total_marks=total_marks,
        max_marks=max_marks,
        percentage=percentage,
        grade=grade
    )


# =========================
# PERFORMANCE CHARTS
# =========================
# =========================
# PERFORMANCE CHARTS
# =========================

@app.route("/charts")
def charts():

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # STUDENT PERFORMANCE
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            SUM(marks.marks) AS total_marks,
            SUM(marks.max_marks) AS max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        GROUP BY students.id, students.student_name
        ORDER BY students.student_name
    """)

    performance_data = cursor.fetchall()

    student_names = []
    percentages = []

    for student in performance_data:

        student_names.append(student["student_name"])

        total_marks = float(student["total_marks"] or 0)
        max_marks = float(student["max_marks"] or 0)

        if max_marks > 0:
            percentage = (total_marks / max_marks) * 100
        else:
            percentage = 0

        percentages.append(round(percentage, 2))


    # =========================
    # ATTENDANCE
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            AVG(attendance.attendance_percentage)
            AS attendance_percentage
        FROM students
        JOIN attendance
        ON students.id = attendance.student_id
        GROUP BY students.id, students.student_name
        ORDER BY students.student_name
    """)

    attendance_data = cursor.fetchall()

    attendance_names = []
    attendance_values = []

    for student in attendance_data:

        attendance_names.append(
            student["student_name"]
        )

        attendance_values.append(
            round(
                float(
                    student["attendance_percentage"] or 0
                ),
                2
            )
        )


    # =========================
    # THEORY MARKS
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            SUM(marks.marks) AS total_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        GROUP BY students.id, students.student_name
        ORDER BY students.student_name
    """)

    marks_data = cursor.fetchall()

    marks_labels = []
    marks_values = []

    for student in marks_data:

        marks_labels.append(
            student["student_name"]
        )

        marks_values.append(
            float(student["total_marks"] or 0)
        )


    # =========================
    # PRACTICAL MARKS
    # =========================

    cursor.execute("""
        SELECT
            students.student_name,
            SUM(practical.marks) AS total_marks
        FROM students
        JOIN practical
        ON students.id = practical.student_id
        GROUP BY students.id, students.student_name
        ORDER BY students.student_name
    """)

    practical_data = cursor.fetchall()

    practical_labels = []
    practical_values = []

    for student in practical_data:

        practical_labels.append(
            student["student_name"]
        )

        practical_values.append(
            float(student["total_marks"] or 0)
        )


    # =========================
    # CLOSE DATABASE
    # =========================

    cursor.close()
    db.close()


    # =========================
    # SEND DATA TO TEMPLATE
    # =========================

    return render_template(
        "charts.html",

        student_names=student_names,
        percentages=percentages,

        attendance_names=attendance_names,
        attendance_values=attendance_values,

        marks_labels=marks_labels,
        marks_values=marks_values,

        practical_labels=practical_labels,
        practical_values=practical_values
    )
# =========================
# RUN APPLICATION
# =========================
# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
import io

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER

# =========================
# DOWNLOAD STUDENT REPORT PDF
# =========================
@app.route("/download-report/<int:student_id>")
def download_report(student_id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # GET STUDENT MARKS
    # =========================

    cursor.execute("""
        SELECT
            students.roll_no,
            students.student_name,
            marks.subject,
            marks.marks,
            marks.max_marks
        FROM students
        JOIN marks
        ON students.id = marks.student_id
        WHERE students.id = %s
        ORDER BY marks.subject
    """, (student_id,))

    report_data = cursor.fetchall()

    cursor.close()
    db.close()

    # No marks found
    if not report_data:
        return "No marks found for this student."

    # =========================
    # CALCULATE RESULT
    # =========================

    total_marks = sum(
        float(row["marks"]) for row in report_data
    )

    max_marks = sum(
        float(row["max_marks"]) for row in report_data
    )

    percentage = 0

    if max_marks > 0:
        percentage = (
            total_marks / max_marks
        ) * 100

    # =========================
    # GRADE
    # =========================

    if percentage >= 90:
        grade = "A+"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 70:
        grade = "B"
    elif percentage >= 60:
        grade = "C"
    elif percentage >= 50:
        grade = "D"
    else:
        grade = "F"

    # =========================
    # CREATE PDF BUFFER
    # =========================

    pdf_buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    # =========================
    # STYLES
    # =========================

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER

    normal_style = styles["Normal"]

    elements = []

    # =========================
    # TITLE
    # =========================

    elements.append(
        Paragraph(
            "STUDENT PERFORMANCE REPORT",
            title_style
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # =========================
    # STUDENT INFORMATION
    # =========================

    elements.append(
        Paragraph(
            f"<b>Student Name:</b> "
            f"{report_data[0]['student_name']}<br/>"
            f"<b>Roll Number:</b> "
            f"{report_data[0]['roll_no']}",
            normal_style
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # =========================
    # MARKS TABLE
    # =========================

    table_data = [
        [
            "Subject",
            "Marks Obtained",
            "Maximum Marks"
        ]
    ]

    for row in report_data:

        table_data.append(
            [
                row["subject"],
                str(row["marks"]),
                str(row["max_marks"])
            ]
        )

    marks_table = Table(
        table_data,
        colWidths=[
            250,
            100,
            100
        ]
    )

    marks_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.black
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                1,
                colors.black
            ),

            (
                "ALIGN",
                (1, 1),
                (-1, -1),
                "CENTER"
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                8
            )
        ])
    )

    elements.append(
        marks_table
    )

    elements.append(
        Spacer(1, 25)
    )

    # =========================
    # RESULT SUMMARY
    # =========================

    elements.append(
        Paragraph(
            f"<b>Total Marks:</b> "
            f"{total_marks:.0f} / {max_marks:.0f}<br/>"
            f"<b>Percentage:</b> "
            f"{percentage:.2f}%<br/>"
            f"<b>Grade:</b> "
            f"{grade}",
            normal_style
        )
    )

    # =========================
    # BUILD PDF
    # =========================

    doc.build(elements)

    # Move pointer to beginning
    pdf_buffer.seek(0)

    # =========================
    # DOWNLOAD PDF
    # =========================

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="student_performance_report.pdf",
        mimetype="application/pdf"
    )
    # =========================
# DELETE STUDENT
# =========================

@app.route("/delete-student/<int:id>")
def delete_student(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM students WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/students")

    # =========================
    # BUILD PDF
    # =========================

    doc.build(elements)

    pdf_buffer.seek(0)

    # =========================
    # DOWNLOAD PDF
    # =========================

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=(
            f"{report_data[0]['student_name']}_Report.pdf"
        ),
        mimetype="application/pdf"
    )
    # =========================
# DOWNLOAD STUDENT REPORT EXCEL
# =========================

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

# =========================
# EDIT MARKS
# =========================

@app.route("/edit-marks/<int:id>", methods=["GET", "POST"])
def edit_marks(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        subject = request.form["subject"]
        marks = request.form["marks"]
        max_marks = request.form["max_marks"]

        try:
            marks = float(marks)
            max_marks = float(max_marks)

            if max_marks <= 0:
                return "Maximum marks must be greater than 0"

            if marks < 0:
                return "Marks cannot be negative"

            if marks > max_marks:
                return "Obtained marks cannot be greater than maximum marks"

        except ValueError:
            return "Please enter valid marks"

        cursor.execute("""
            UPDATE marks
            SET
                subject = %s,
                marks = %s,
                max_marks = %s
            WHERE id = %s
        """, (
            subject,
            marks,
            max_marks,
            id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect("/marks")

    cursor.execute("""
        SELECT
            marks.id,
            marks.subject,
            marks.marks,
            marks.max_marks,
            students.student_name,
            students.roll_no
        FROM marks
        JOIN students
        ON students.id = marks.student_id
        WHERE marks.id = %s
    """, (id,))

    mark = cursor.fetchone()

    cursor.close()
    db.close()

    if not mark:
        return "Marks record not found"

    return render_template(
        "edit_marks.html",
        mark=mark
    )
    
    # =========================
# DELETE MARKS
# =========================

@app.route("/delete-marks/<int:id>")
def delete_marks(id):

    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM marks WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/marks")
# =========================
# OVERALL STUDENT PERFORMANCE
# =========================

@app.route("/overall-performance")
def overall_performance():


    if "user_id" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # =========================
    # STUDENT LIST
    # =========================

    cursor.execute("""
        SELECT id, roll_no, student_name
        FROM students
        ORDER BY student_name
    """)

    students_data = cursor.fetchall()

    # =========================
    # DEFAULT VALUES
    # =========================

    student = None

    theory_percentage = 0.0
    practical_percentage = 0.0
    assignment_percentage = 0.0
    attendance_percentage = 0.0

    overall_percentage = 0.0
    grade = "N/A"
    
    performance_status = "N/A"
    weak_area = "N/A"
    improvement_message = "No performance data available."

    activity_count = 0
    participation_count = 0

    # =========================
    # SELECTED STUDENT
    # =========================

    student_id = request.args.get("student_id")

    if student_id:

        # =========================
        # STUDENT DETAILS
        # =========================

        cursor.execute("""
            SELECT *
            FROM students
            WHERE id = %s
        """, (student_id,))

        student = cursor.fetchone()

        if student:

            # =========================
            # THEORY
            # =========================

            cursor.execute("""
                SELECT
                    COALESCE(SUM(marks), 0) AS total_marks,
                    COALESCE(SUM(max_marks), 0) AS max_marks
                FROM marks
                WHERE student_id = %s
            """, (student_id,))

            theory = cursor.fetchone()

            theory_total = float(
                theory["total_marks"] or 0
            )

            theory_max = float(
                theory["max_marks"] or 0
            )

            if theory_max > 0:

                theory_percentage = (
                    theory_total / theory_max
                ) * 100


            # =========================
            # PRACTICAL
            # =========================

            cursor.execute("""
                SELECT
                    COALESCE(SUM(marks), 0) AS total_marks,
                    COALESCE(SUM(max_marks), 0) AS max_marks
                FROM practical
                WHERE student_id = %s
            """, (student_id,))

            practical = cursor.fetchone()

            practical_total = float(
                practical["total_marks"] or 0
            )

            practical_max = float(
                practical["max_marks"] or 0
            )

            if practical_max > 0:

                practical_percentage = (
                    practical_total / practical_max
                ) * 100


            # =========================
            # ASSIGNMENT
            # =========================

            cursor.execute("""
                SELECT
                    COALESCE(SUM(marks), 0) AS total_marks,
                    COALESCE(SUM(max_marks), 0) AS max_marks
                FROM assignments
                WHERE student_id = %s
            """, (student_id,))

            assignment = cursor.fetchone()

            assignment_total = float(
                assignment["total_marks"] or 0
            )

            assignment_max = float(
                assignment["max_marks"] or 0
            )

            if assignment_max > 0:

                assignment_percentage = (
                    assignment_total / assignment_max
                ) * 100


            # =========================
            # ATTENDANCE
            # =========================

            cursor.execute("""
                SELECT
                    AVG(attendance_percentage)
                    AS attendance_percentage
                FROM attendance
                WHERE student_id = %s
            """, (student_id,))

            attendance = cursor.fetchone()

            attendance_value = attendance[
                "attendance_percentage"
            ]

            if attendance_value is not None:

                attendance_percentage = float(
                    attendance_value
                )


            # =========================
            # ACTIVITY COUNT
            # =========================

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM activities
                WHERE student_id = %s
            """, (student_id,))

            activity_count = cursor.fetchone()["total"]


            # =========================
            # PARTICIPATION COUNT
            # =========================

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM participation
                WHERE student_id = %s
            """, (student_id,))

            participation_count = cursor.fetchone()["total"]


            # =========================
            # OVERALL PERFORMANCE
            # =========================

            components = []

            if theory_max > 0:
                components.append(
                    float(theory_percentage)
                )

            if practical_max > 0:
                components.append(
                    float(practical_percentage)
                )

            if assignment_max > 0:
                components.append(
                    float(assignment_percentage)
                )

            if attendance_value is not None:
                components.append(
                    float(attendance_percentage)
                )

            if len(components) > 0:

                overall_percentage = (
                    sum(components)
                    / len(components)
                )
           # =========================
           # PERFORMANCE STATUS
           # =========================

            if overall_percentage >= 75:
             performance_status = "Good Performance"
            elif overall_percentage >= 50:
                performance_status = "Average Performance"
            else:
                performance_status = "Needs Improvement"
                
            # =========================
            # WEAK AREA
            # =========================

            performance_components = {
                "Theory": theory_percentage,
                "Practical": practical_percentage,
                "Assignment": assignment_percentage,
                "Attendance": attendance_percentage
                }
            
            available_components = {
                name: percentage
                for name, percentage in performance_components.items()
                if percentage > 0
                }
            if available_components:
                weak_area = min(
                    available_components,
                    key=available_components.get
                    )
            else:
                weak_area = "N/A"

            # =========================
            # IMPROVEMENT MESSAGE
            # =========================

            if weak_area == "Theory":
                improvement_message = (
                    "Focus more on theory subjects and regular revision."
                    )
            elif weak_area == "Practical":
                improvement_message = (
                    "Practice more practical exercises and lab work."
                    )
            elif weak_area == "Assignment":
                improvement_message = (
                    "Complete assignments regularly and improve submission quality."
                    )
            elif weak_area == "Attendance":
                improvement_message = (
                    "Improve class attendance and maintain regular participation."
                    )
            else:
                improvement_message = (
                    "Keep maintaining your academic performance."
                    )
            # =========================
            # GRADE
            # =========================

            if overall_percentage >= 90:

                grade = "A+"

            elif overall_percentage >= 80:

                grade = "A"

            elif overall_percentage >= 70:

                grade = "B"

            elif overall_percentage >= 60:

                grade = "C"

            elif overall_percentage >= 50:

                grade = "D"

            else:

                grade = "F"


    # =========================
    # CLOSE DATABASE
    # =========================

    cursor.close()
    db.close()


    # =========================
    # SEND DATA TO TEMPLATE
    # =========================

    return render_template(
        "overall_performance.html",

        students=students_data,

        student=student,

        theory_percentage=round(
            float(theory_percentage),
            2
        ),

        practical_percentage=round(
            float(practical_percentage),
            2
        ),

        assignment_percentage=round(
            float(assignment_percentage),
            2
        ),

        attendance_percentage=round(
            float(attendance_percentage),
            2
        ),

        overall_percentage=round(
            float(overall_percentage),
            2
        ),

        grade=grade,
        
        performance_status=performance_status,

        weak_area=weak_area,

        improvement_message=improvement_message,

        activity_count=activity_count,

        participation_count=participation_count
    )

# =========================
# RUN APPLICATION 
# =========================
# CREATE HASHED ADMIN PASSWORD
# =========================

if __name__ == "__main__":
    app.run(debug=True)