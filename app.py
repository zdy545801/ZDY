import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
import random
from flask import session


app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    message = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        if len(username) < 3 or len(password) < 6:
            message = "用户名或密码长度不符合要求"
        else:
            conn = get_db_connection()
            existing = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if existing:
                message = "用户名已存在，请换一个"
            else:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                conn.commit()
                conn.close()
                return redirect(url_for('login', success='1'))
            conn.close()
    return render_template('register.html', message=message)

@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    error = None
    if request.method == 'POST':
        code = request.form['code']
        if code != session.get('reset_code'):
            error = '验证码错误'
        else:
            return redirect(url_for('reset_password_confirm'))
    return render_template('verify_code.html', error=error)

@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    message = None
    error = None

    if request.method == 'POST':
        if 'get_code' in request.form:
            username = request.form['username'].strip()
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            conn.close()

            if user:
                code = str(random.randint(100000, 999999))
                session['reset_code'] = code
                session['reset_username'] = username
                print("验证码为：", code)
                message = f"验证码已生成：{code}（仅测试显示）"
            else:
                error = "用户名不存在"

        elif 'verify_code' in request.form:
            entered = request.form['verify_code'].strip()
            if entered == session.get('reset_code'):
                return redirect(url_for('reset_password_confirm'))
            else:
                error = "验证码错误，请重新输入"

    return render_template('forgot.html', message=message, error=error)



@app.route('/reset_password_confirm', methods=['GET', 'POST'])
def reset_password_confirm():
    if 'reset_username' not in session:
        return redirect(url_for('forgot_password'))

    error = None
    if request.method == 'POST':
        pwd = request.form['password']
        confirm = request.form['confirm']
        if pwd != confirm:
            error = '两次密码不一致'
        elif len(pwd) < 6:
            error = '密码太短，至少6位'
        else:
            conn = get_db_connection()
            conn.execute('UPDATE users SET password = ? WHERE username = ?', (pwd, session['reset_username']))
            conn.commit()
            conn.close()
            session.pop('reset_username')
            session.pop('reset_code', None)  # 清理验证码
            return redirect(url_for('login', reset='1'))

    return render_template('reset_password_confirm.html', error=error)



@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['user_input']
        password = request.form['pass_input']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username=? AND password=?',
                            (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard', login='1'))
        else:
            error = '用户名或密码错误，请重试'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index', logout='1'))

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        avatar_file = request.files.get('avatar')

        avatar_filename = user['avatar'] or 'default.png'

        if avatar_file and allowed_file(avatar_file.filename):
            avatar_filename = secure_filename(avatar_file.filename)
            avatar_file.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))

        conn.execute('''
            UPDATE users SET username = ?, password = ?, avatar = ?
            WHERE id = ?
        ''', (new_username, new_password, avatar_filename, session['user_id']))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('account.html', user=user)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT username, avatar FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    return render_template('user_home.html',
                           username=user['username'],
                           user_avatar=user['avatar'] or 'default.png')





@app.route('/booking', methods=['GET', 'POST'])  #预约
def booking():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_id = session['user_id']
        date = request.form['date']
        time = request.form['time']
        service = request.form['service']
        car_model = request.form['car_model']
        license_plate = request.form['license_plate']
        repair_method = request.form['repair_method']

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO bookings (user_id, date, time, service, car_model, license_plate, repair_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, date, time, service, car_model, license_plate, repair_method))
        conn.commit()
        conn.close()

        return redirect(url_for('booking') + '?success=1')

    return render_template('booking.html')



@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT 
            b.*, 
            EXISTS (
                SELECT 1 FROM reviews r 
                WHERE r.booking_id = b.id
            ) AS has_review
        FROM bookings b
        WHERE b.user_id = ?
        ORDER BY b.date DESC, b.time DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('my_bookings.html', bookings=bookings)


@app.route('/cancel_booking', methods=['POST'])  #用户取消预约
def cancel_booking():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    booking_id = request.form['booking_id']
    conn = get_db_connection()
    # 只能取消状态为“待确认”的预约
    conn.execute('DELETE FROM bookings WHERE id = ? AND user_id = ? AND status = "待确认"',
                 (booking_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('my_bookings', cancel='1'))


@app.route('/peak_times')
def peak_times():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # 上方图表数据（每天预约人数）
    daily = conn.execute('''
        SELECT date, COUNT(*) as count
        FROM bookings
        GROUP BY date
        ORDER BY date
    ''').fetchall()

    labels = [row['date'] for row in daily]
    counts = [row['count'] for row in daily]

    # 表格明细数据（日期+时间+人数）
    details = conn.execute('''
        SELECT date, time, COUNT(*) as count
        FROM bookings
        GROUP BY date, time
        ORDER BY count DESC
    ''').fetchall()

    conn.close()

    return render_template(
        'peak_times.html',
        labels=labels,
        counts=counts,
        details=details
    )

@app.route('/notices')
def user_notices():
    conn = get_db_connection()
    notices = conn.execute('SELECT * FROM notices ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('user_notices.html', notices=notices)

@app.route('/rate/<int:booking_id>', methods=['GET', 'POST'])
def rate_booking(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # 防止重复评价
    existing = conn.execute('SELECT id FROM reviews WHERE booking_id = ?', (booking_id,)).fetchone()
    if existing:
        conn.close()
        return '该预约已提交评价，无需重复。'

    if request.method == 'POST':
        stars = int(request.form['rating'])
        comment = request.form.get('feedback', '')

        conn.execute('''
            INSERT INTO reviews (user_id, booking_id, stars, comment)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], booking_id, stars, comment))

        # 也可以更新预约状态
        conn.execute('UPDATE bookings SET status = "已完成" WHERE id = ?', (booking_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('my_bookings', rated='1'))


    booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
    conn.close()
    return render_template('rate_booking.html', booking=booking)




@app.route('/my_reviews')
def my_reviews():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    reviews = conn.execute('''
        SELECT 
            r.stars, 
            r.comment, 
            r.date AS review_date, 
            b.date AS booking_date, 
            b.time, 
            b.service
        FROM reviews r
        JOIN bookings b ON r.booking_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.date DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('my_reviews.html', reviews=reviews)



@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('admin_input')
        password = request.form.get('admin_pass')

        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            return redirect(url_for('admin_home', success='1'))
        else:
            error = '管理员登录失败，请检查账号或密码'

    return render_template('admin_login.html', error=error)


@app.route('/admin')
def admin_home():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin_home.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT 
            b.id,                
            b.date,
            b.time,
            b.service,
            b.car_model,
            b.license_plate,
            b.status,
            u.username
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        ORDER BY b.date ASC, b.time ASC, u.username ASC
    ''').fetchall()
    conn.close()

    return render_template('admin_dashboard.html', bookings=bookings)




@app.route('/admin/update_status', methods=['POST']) #管理员更新状态
def update_status():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    booking_id = request.form.get('booking_id')
    new_status = request.form.get('status')

    # 打印调试信息（可选）
    print(f"更新预约 ID {booking_id} 的状态为 {new_status}")

    conn = get_db_connection()
    conn.execute('UPDATE bookings SET status = ? WHERE id = ?', (new_status, booking_id))
    conn.commit()
    conn.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/peak_times')
def admin_peak_times():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    # 上方柱状图数据（每天总预约人数）
    daily = conn.execute('''
        SELECT date, COUNT(*) as count
        FROM bookings
        GROUP BY date
        ORDER BY date
    ''').fetchall()

    dates = [row['date'] for row in daily]
    counts = [row['count'] for row in daily]

    # 下方表格数据（明细：日期 + 时间 + 人数，按人数排序）
    details = conn.execute('''
        SELECT date, time, COUNT(*) as count
        FROM bookings
        GROUP BY date, time
        ORDER BY count DESC
    ''').fetchall()

    conn.close()

    return render_template(
        'admin_peak_times.html',
        dates=dates,
        counts=counts,
        details=details  #
    )

@app.route('/admin/reviews')
def admin_reviews():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    reviews = conn.execute('''
        SELECT r.id, r.stars, r.comment, r.date, u.username
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.date DESC
    ''').fetchall()
    conn.close()

    return render_template('admin_reviews.html', reviews=reviews)


@app.route('/admin/news', methods=['GET', 'POST'])
def admin_news():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn.execute('INSERT INTO notices (title, content) VALUES (?, ?)', (title, content))
        conn.commit()
        conn.close()
        # ✅ 关键：发布完后重定向到 GET，携带 success 参数，页面会自动加载最新公告
        return redirect(url_for('admin_news', success='1'))

    # ✅ GET 请求：从数据库加载最新公告
    notices = conn.execute('SELECT * FROM notices ORDER BY created_at DESC').fetchall()
    conn.close()

    return render_template('admin_news.html', notices=notices)






if __name__ == '__main__':
    app.run(debug=True)

