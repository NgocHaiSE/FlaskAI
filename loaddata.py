from MySQLConnector import getConnector

# Kết nối tới MySQL
conn =getConnector()

# Tạo một đối tượng cursor
cursor = conn.cursor()

# Thực hiện truy vấn
cursor.execute("SELECT image.link,person.id, person.idperson FROM image INNER JOIN person ON image.id_person = person.id")

# Lấy tất cả kết quả
results = cursor.fetchall()

# In kết quả
for row in results:
    print(row)

# Đóng kết nối
cursor.close()
conn.close()
