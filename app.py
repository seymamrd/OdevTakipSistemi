from flask import Flask, render_template, request, redirect, session, flash, url_for, send_from_directory
import pymysql
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_key"

UPLOAD_FOLDER = "static/uploads"

### alltaki satır ile ilgili sorun olabilir unutma
ALLOWED_EXTENSIONS = {'pdf', 'zip', 'rar', 'txt', 'jpg', 'jpeg', 'png', 'webp'}
###
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



# ---------- DATABASE CONNECTION ----------
def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="sm12345678",
        database="school_db",
        cursorclass=pymysql.cursors.DictCursor
    )


# ---------- LOGIN PAGE ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        password = request.form['password']

        conn = get_connection()
        cur = conn.cursor()

        # 🚨 Rol seçilmemişse uyarı ver
        if not role:
            flash(("warning", "Lütfen bir rol seçiniz!"))
            return render_template('login.html')

        # 👑 Admin login
        if role == 'admin':
            if request.form['email'] == 'admin@okul.com' and password == '12345':
                session['admin'] = True
                return redirect('/admin')
            else:
                flash(("error", "Admin bilgileri hatalı!"))

        # 👨‍🏫 Öğretmen login
        elif role == 'teacher':
            cur.execute("SELECT * FROM teachers WHERE email=%s AND password=%s",
                        (request.form['email'], password))
            teacher = cur.fetchone()
            if teacher:
                session['teacher_id'] = teacher['id']
                return redirect('/teacher')
            else:
                flash(("error", "E-posta veya şifre hatalı!"))

        # 🎓 Öğrenci login
        elif role == 'student':
            cur.execute("SELECT * FROM students WHERE tc_no=%s AND password=%s",
                        (request.form['tc_no'], password))
            student = cur.fetchone()
            if student:
                session['student_id'] = student['id']
                return redirect('/student')
            else:
                flash(("error", "TC veya şifre hatalı!"))

        conn.close()

    return render_template('login.html')


# ---------- ADMIN PANEL ----------
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'admin' not in session:
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor()

    # Öğretmen veya öğrenci ekleme
    if request.method == 'POST':
        if request.form['type'] == 'teacher':
            cur.execute("""INSERT INTO teachers (name, email, password, branch)
                        VALUES (%s, %s, %s, %s)""",
                        (request.form['name'], request.form['email'],
                         request.form['password'], request.form['branch']))
        elif request.form['type'] == 'student':
            cur.execute("""INSERT INTO students (name, tc_no, password, classroom)
                        VALUES (%s, %s, %s, %s)""",
                        (request.form['name'], request.form['tc_no'],
                         request.form['password'], request.form['classroom']))
        conn.commit()

    # Listeleme
    cur.execute("SELECT * FROM teachers")
    teachers = cur.fetchall()
    cur.execute("SELECT * FROM students")
    students = cur.fetchall()

    conn.close()
    return render_template('admin.html', teachers=teachers, students=students)


# ---------- TEACHER PANEL ----------
@app.route('/teacher', methods=['GET', 'POST'])
def teacher_panel():
    if 'teacher_id' not in session:
        return redirect('/')

    conn = get_connection()
    cursor = conn.cursor()

    teacher_id = session['teacher_id']

    # 🟢 Öğretmen bilgileri
    cursor.execute("SELECT * FROM teachers WHERE id=%s", (teacher_id,))
    teacher = cursor.fetchone()

    # 🟢 Yeni ödev yükleme
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        classroom = request.form['classroom']
        file = request.files['file']
        deadline = request.form['deadline']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            cursor.execute("""
                INSERT INTO assignments (title, description, filename, teacher_id, classroom, upload_date, deadline)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (title, description, filename, teacher_id, classroom, datetime.now(), deadline))
            conn.commit()
            flash("Ödev başarıyla yüklendi.", "success")
        else:
            flash("Dosya türü geçersiz! Sadece pdf, zip, rar, txt kabul edilir.", "danger")

    # 🟢 Öğretmenin yüklediği ödevler
    cursor.execute("""
        SELECT id, title, description, filename, classroom, upload_date, deadline
        FROM assignments
        WHERE teacher_id = %s
        ORDER BY upload_date DESC
    """, (teacher_id,))
    assignments = cursor.fetchall()

    # 🟢 Öğrencilerin yaptığı ödevler
    cursor.execute("""
        SELECT s.filename, s.upload_date, st.id AS student_id, st.name AS student_name, st.classroom, a.id AS assignment_id, a.title AS assignment_title
        FROM submissions s
        JOIN students st ON s.student_id = st.id
        JOIN assignments a ON s.assignment_id = a.id
        WHERE a.teacher_id = %s
        ORDER BY s.upload_date DESC
    """, (teacher_id,))
    submissions = cursor.fetchall()


    # 🟢 Sınıf listesi (filtreleme için)
    cursor.execute("""
        SELECT DISTINCT classroom FROM (
            SELECT classroom FROM assignments WHERE teacher_id=%s
            UNION
            SELECT st.classroom FROM submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.id
            WHERE a.teacher_id = %s
        ) AS all_classes
    """, (teacher_id, teacher_id))
    class_list = [row['classroom'] for row in cursor.fetchall()]

        # 🟢 Her ödev için teslim eden ve etmeyen öğrencileri bul
    for a in assignments:
        classroom = a["classroom"]
        assignment_id = a["id"]

        cursor.execute("SELECT id, name FROM students WHERE classroom = %s", (classroom,))
        students_in_class = cursor.fetchall()

        submitted_ids = [
            s["student_id"] for s in submissions if s["assignment_id"] == assignment_id
        ]

        a["submitted_students"] = [s for s in students_in_class if s["id"] in submitted_ids]
        a["missing_students"] = [s for s in students_in_class if s["id"] not in submitted_ids]


    cursor.close()
    conn.close()

    return render_template(
        'teacher.html',
        teacher=teacher,
        assignments=assignments,
        submissions=submissions,
        class_list=class_list,
        now=datetime.now
    )


# 🗑️ Ödev silme
@app.route('/delete_assignment/<int:assignment_id>')
def delete_assignment(assignment_id):
    if 'teacher_id' not in session:
        return redirect('/')
    
    conn = get_connection()
    cursor = conn.cursor()

    # Dosya adını bul
    cursor.execute("SELECT filename FROM assignments WHERE id=%s", (assignment_id,))
    file = cursor.fetchone()
    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)

    cursor.execute("DELETE FROM assignments WHERE id=%s", (assignment_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Ödev silindi.", "success")
    return redirect(url_for('teacher_panel'))

#Öğretmen ödev düzenleme
@app.route('/edit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
def edit_assignment(assignment_id):
    if 'teacher_id' not in session:
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor()
    
    # Mevcut ödevi getir
    cur.execute("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
    assignment = cur.fetchone()
    
    if not assignment:
        flash("Ödev bulunamadı.", "error")
        return redirect('/teacher')

    if request.method == 'POST':
        title = request.form['title']
        classroom = request.form['classroom']
        deadline = request.form['deadline']
        description = request.form['description']

        cur.execute("""
            UPDATE assignments 
            SET title = %s, classroom = %s, deadline = %s, description = %s 
            WHERE id = %s
        """, (title, classroom, deadline, description, assignment_id))
        conn.commit()
        flash("Ödev başarıyla güncellendi.", "success")
        return redirect('/teacher')

    return render_template('edit_assignment.html', assignment=assignment)


# 💾 Dosya indirme
@app.route('/download/<filename>')
def download_file(filename):
    # önce uploads klasöründe ara
    uploads_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    submissions_path = os.path.join("static/submissions", filename)

    if os.path.exists(uploads_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    elif os.path.exists(submissions_path):
        return send_from_directory("static/submissions", filename, as_attachment=True)
    else:
        flash("Dosya bulunamadı!", "danger")
        return redirect(request.referrer)

#----------- ÖĞRETMEN SİLME FONKSİYONU ----------------------
@app.route('/delete_teacher/<int:teacher_id>')
def delete_teacher(teacher_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM teachers WHERE id=%s", (teacher_id,))
    conn.commit()
    cursor.close()
    return redirect(url_for('admin_panel', message="Öğretmen silindi", message_type="success"))

#----------- ÖĞRENCİ SİLME FONKSİYONU ----------------------
@app.route('/delete_student/<int:student_id>')
def delete_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
    conn.commit()
    cursor.close()
    return redirect(url_for('admin_panel', message="Öğrenci silindi", message_type="success"))



# ---------- STUDENT PANEL ----------
@app.route('/student', methods=['GET', 'POST'])
def student_panel():
    if 'student_id' not in session:
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor()
    student_id = session['student_id']

    # Öğrencinin sınıfını al
    cur.execute("SELECT classroom FROM students WHERE id=%s", (student_id,))
    classroom = cur.fetchone()['classroom']


    cur.execute("""
        SELECT a.*, t.name AS teacher_name, t.branch,
               s.filename AS submitted_file, s.upload_date AS submitted_date
        FROM assignments a
        JOIN teachers t ON a.teacher_id = t.id
        LEFT JOIN submissions s 
            ON s.assignment_id = a.id AND s.student_id = %s
        WHERE a.classroom=%s
        ORDER BY a.upload_date DESC
        """, (student_id, classroom))
    assignments = cur.fetchall()

    # 🟢 Ödev yükleme işlemi
    if request.method == 'POST':
        assignment_id = request.form['assignment_id']
        file = request.files['file']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join("static/submissions", filename)
            file.save(upload_path)

            # 🔍 Daha önce aynı ödevi yüklemiş mi?
            cur.execute("""
                SELECT id FROM submissions
                WHERE assignment_id=%s AND student_id=%s
            """, (assignment_id, student_id))
            existing = cur.fetchone()

            if existing:
                # Güncelle
                cur.execute("""
                    UPDATE submissions
                    SET filename=%s, upload_date=%s
                    WHERE id=%s
                """, (filename, datetime.now(), existing['id']))
                flash("Ödev başarıyla güncellendi.", "success")
            else:
                # Öğrencinin o ödevi daha önce yükleyip yüklemediğini kontrol et
                cur.execute("""
                    SELECT id FROM submissions
                    WHERE assignment_id=%s AND student_id=%s
                """, (assignment_id, student_id))
                existing = cur.fetchone()

                if existing:
                    # Güncelleme yap
                    cur.execute("""
                        UPDATE submissions
                        SET filename=%s, upload_date=%s
                        WHERE id=%s
                    """, (filename, datetime.now(), existing['id']))
                    flash("Ödev başarıyla güncellendi ✅", "success")
                else:
                    # Yeni yükleme yap
                    cur.execute("""
                        INSERT INTO submissions (assignment_id, student_id, filename, upload_date)
                        VALUES (%s, %s, %s, %s)
                    """, (assignment_id, student_id, filename, datetime.now()))
                    flash("Ödev başarıyla yüklendi ✅", "success")


            conn.commit()
        else:
            flash("Geçersiz dosya türü!", "danger")

    # Öğrencinin daha önce yüklediği ödevleri getir
    cur.execute("SELECT * FROM submissions WHERE student_id=%s", (student_id,))
    submissions = cur.fetchall()

    conn.close()
    return render_template('student.html', assignments=assignments, submissions=submissions, now=datetime.now)


# ---------- DOSYA İNDİRME ----------
# @app.route('/download/<filename>')
# def download_file(filename):
#     return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


# ---------- ÇIKIŞ ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
