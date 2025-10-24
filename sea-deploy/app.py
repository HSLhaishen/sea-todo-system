from flask import Flask, request, redirect, url_for, render_template, session, flash
import os
import sqlite3
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# 配置文件上传
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# 数据库配置
DB_FILE = "todo_app.db"

# 分类和颜色配置
COLOR_MAP = {
    '工作': '#ff0000',
    '学习': '#f47505', 
    '生活': '#dbfc00',
    '购物': '#00FA15',
    '健康': '#008CFF',
    '娱乐': '#0509FA',
    '通用': '#9500FF'
}
CATEGORIES = list(COLOR_MAP.keys())

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # 创建用户表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # 创建任务表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            category TEXT DEFAULT '通用',
            done BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成！")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 初始化数据库
print("🚀 应用程序启动中...")
init_db()

# ========== 路由定义 ==========

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()
        
        print(f"🔍 注册尝试 - 用户名: '{username}'")
        
        # 基本验证
        if not username or not password:
            return render_template('register.html', error='用户名和密码不能为空')
        if password != confirm_password:
            return render_template('register.html', error='两次输入的密码不一致')
        if len(username) < 3:
            return render_template('register.html', error='用户名至少3个字符')
        if len(password) < 6:
            return render_template('register.html', error='密码至少6个字符')
        
        try:
            conn = get_db_connection()
            
            # 检查用户名是否存在
            existing_user = conn.execute(
                'SELECT * FROM users WHERE username = ?', 
                (username,)
            ).fetchone()
            
            if existing_user:
                conn.close()
                return render_template('register.html', error='用户名已存在')
            
            # 创建新用户
            conn.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, password)
            )
            conn.commit()
            conn.close()
            
            return render_template('register.html', success='注册成功！请前往登录')
            
        except Exception as e:
            return render_template('register.html', error='注册过程出错，请重试')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        print(f'🔍 登录尝试: 用户名="{username}"')
        
        try:
            conn = get_db_connection()
            user = conn.execute(
                'SELECT * FROM users WHERE username = ?',
                (username,)
            ).fetchone()
            conn.close()
            
            if user:
                # 简化：不验证密码（学习阶段）
                session['username'] = username
                session['logged_in'] = True
                session['user_id'] = user['id']
                flash('登录成功', 'success')
                return redirect(url_for('show_todos'))
            else:
                return render_template('login.html', error='用户不存在')
                
        except Exception as e:
            return render_template('login.html', error='登录过程出错,请重试')
    
    return render_template('login.html')

@app.route('/todos')
def show_todos():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    username = session.get('username')
    user_id = session.get('user_id')
    
    # 从数据库获取用户任务
    conn = get_db_connection()
    todos = conn.execute(
        'SELECT * FROM todos WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    
    # 转换为字典列表
    user_todos = []
    for todo in todos:
        user_todos.append({
            'id': todo['id'],
            'task': todo['task'],
            'category': todo['category'],
            'done': bool(todo['done']),
            'priority': '中'
        })
    
    # 筛选逻辑
    filter_category = request.args.get('filter', '全部')
    filtered_todos = user_todos
    if filter_category != '全部':
        filtered_todos = [task for task in user_todos if task.get('category') == filter_category]
    
    # 统计信息
    total_tasks = len(user_todos)
    completed_tasks = len([t for t in user_todos if t.get('done')])
    completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
    
    return render_template('todos.html', 
                         todos=filtered_todos, 
                         username=username, 
                         color_map=COLOR_MAP,
                         categories=CATEGORIES,
                         current_filter=filter_category,
                         completion_rate=completion_rate)

@app.route('/add', methods=['POST'])
def add_todo():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    task = request.form.get('task', '').strip()
    category = request.form.get('category', '通用')
    
    if task:
        image_filename = None
        if 'task_image' in request.files:
            file = request.files['task_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                image_filename = f"{name}_{timestamp}{ext}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, image_filename))
        
        # 使用数据库插入
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO todos (user_id, task, category) VALUES (?, ?, ?)',
            (user_id, task, category)
        )
        conn.commit()
        conn.close()
    
    return redirect(url_for('show_todos'))

@app.route('/delete/<int:todo_id>')
def delete_todo(todo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    conn.execute('DELETE FROM todos WHERE id = ? AND user_id = ?', (todo_id, user_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('show_todos'))

@app.route('/toggle/<int:todo_id>')
def toggle_todo(todo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    todo = conn.execute('SELECT * FROM todos WHERE id = ? AND user_id = ?', (todo_id, user_id)).fetchone()
    if todo:
        new_done = not todo['done']
        conn.execute('UPDATE todos SET done = ? WHERE id = ?', (new_done, todo_id))
        conn.commit()
    conn.close()
    
    return redirect(url_for('show_todos'))

@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))

# 调试路由
@app.route('/debug_users')
def debug_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    result = []
    for user in users:
        result.append(f"ID: {user['id']}, 用户名: '{user['username']}'")
    conn.close()
    return '<br>'.join(result)

@app.route('/health')
def health_check():
    return "✅ 应用运行正常！"

if __name__ == '__main__':
    app.run(debug=False, port=5000)