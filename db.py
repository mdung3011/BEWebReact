import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="10.73.132.85",      # hoặc localhost
        port=3306,             # 👉 cổng mặc định MySQL, sửa nếu khác
        user="root",           # tài khoản MySQL của bạn
        password="1234",           # mật khẩu MySQL của bạn
        database="sdvn"   # tên database
    )