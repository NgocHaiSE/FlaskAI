import random
from datetime import date, timedelta
import mysql.connector

# Kết nối MySQL
def getConnector():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="08032003",
        database="face_application"
    )
    return conn

statuses = ['PRESENT', 'LATE', 'LEFT_EARLY', 'ABSENT', 'ON_LEAVE']
num_employees = 10
start_date = date(2025, 3, 1)
end_date = date(2025, 3, 31)

# Sinh dữ liệu
rows = []
for pid in range(1, num_employees + 1):
    d = start_date
    while d <= end_date:
        status = random.choice(statuses)
        if status in ['PRESENT', 'LATE', 'LEFT_EARLY']:
            first_in = f"{d} 08:{random.randint(0, 59):02}:00"
            last_out = f"{d} {random.randint(16, 19):02}:{random.randint(0, 59):02}:00"
            total_work_min = random.randint(350, 700)
        else:
            first_in = None
            last_out = None
            total_work_min = 0
        rows.append((
            pid,
            str(d),
            first_in,
            last_out,
            total_work_min,
            status,
            None  # photo_url
        ))
        d += timedelta(days=1)

# Insert vào MySQL
conn = getConnector()
cursor = conn.cursor()
# Xóa dữ liệu cũ trong tháng 5 của các nhân viên test (1-5)
cursor.execute("""
    DELETE FROM AttendanceDaily
    WHERE work_date BETWEEN '2025-03-01' AND '2025-03-31'
    AND person_id BETWEEN %s AND %s
""", (1, num_employees))

sql = """
INSERT INTO AttendanceDaily
(person_id, work_date, first_in_time, last_out_time, total_work_min, status, photo_url, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
"""

cursor.executemany(sql, rows)
conn.commit()
print(f"Đã insert {cursor.rowcount} dòng vào bảng AttendanceDaily cho tháng 5/2025.")

cursor.close()
conn.close()
