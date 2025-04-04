import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3

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

@app.route('/register', methods=['GET', 'POST'])  #注册
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])  # 登录
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username=? AND password=?',
                            (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            error = '用户名或密码错误，请重试'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

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
        vehicle_info = request.form['vehicle_info']
        repair_method = request.form['repair_method']

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO bookings (user_id, date, time, service, vehicle_info, repair_method)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, date, time, service, vehicle_info, repair_method))
        conn.commit()
        conn.close()

        # ✅ 添加跳转提示
        return redirect(url_for('dashboard', success='1'))

    return render_template('booking.html')



@app.route('/my_bookings') #用户查看预约
def my_bookings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT * FROM bookings WHERE user_id = ?
        ORDER BY date DESC, time DESC
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
    return redirect(url_for('my_bookings'))

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



@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            return redirect(url_for('admin_home'))  # ✅ 登录成功跳转主页
        else:
            return '管理员登录失败'
    return render_template('admin_login.html')

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
            b.vehicle_info,
            b.status,
            u.username
        FROM bookings b
        JOIN users u ON b.user_id = u.id
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




if __name__ == '__main__':
    app.run(debug=True)

