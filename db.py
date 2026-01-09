import pymysql

conn = pymysql.connect(
    host = "localhost",
    user = "root",
    password = "sm12345678"
)

cursor = conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS school_db")
cursor.execute("USE school_db")


#ÖĞRETMENLER TABLOSUU
cursor.execute("""
CREATE TABLE IF NOT EXISTS teachers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                branch VARCHAR(100) NOT NULL
               )
               """)

#ÖĞRENC TABLOSU
cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
               id INT AUTO_INCREMENT PRIMARY KEY,
               name VARCHAR(100) NOT NULL,
               tc_no VARCHAR(11) UNIQUE NOT NULL,
               password VARCHAR(100) NOT NULL,
               classroom VARCHAR(50) NOT NULL
               )
               """)

#ÖDEV TABLOSU
cursor.execute("""
CREATE TABLE IF NOT EXISTS assignments (
               id INT AUTO_INCREMENT PRIMARY KEY,
               title VARCHAR(200),
               description TEXT,
               filename VARCHAR(200),
               teacher_id INT,
               classroom VARCHAR(50),
               upload_date DATETIME,
               deadline DATETIME,
               FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
               )
               """)

# ÖDEV YÜKLEME TABLOSU
cursor.execute("""
CREATE TABLE IF NOT EXISTS submissions (
               id INT AUTO_INCREMENT PRIMARY KEY,
               assignment_id INT,
               student_id INT,
               filename VARCHAR(200),
               upload_date DATETIME,
               FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
               FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
               )
               """)

conn.commit()
print("Veritabanı ve tablo oluşturuldu.")
cursor.close()
conn.close()