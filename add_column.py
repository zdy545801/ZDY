import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# 添加 repair_method 字段
try:
    cursor.execute('ALTER TABLE bookings ADD COLUMN repair_method TEXT')
    print("字段 'repair_method' 添加成功！")
except Exception as e:
    print("添加失败：", e)

conn.commit()
conn.close()
