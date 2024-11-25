from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_mysql_connector import MySQL
import os
import random
import string

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app)

# MySQL Configuration (updated to remove UTF-8 configuration)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'demon'
app.config['MYSQL_DATABASE'] = 'videom'
# Do not specify a charset or explicitly set it to non-UTF-8 like latin1
app.config['MYSQL_CHARSET'] = 'latin1'  # Change this if necessary

mysql = MySQL(app)

# Folder for uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'mp4', 'mkv', 'avi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the uploaded file is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home Route
@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            mysql.connection.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            cursor.close()
    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT password FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if user and user[0] == password:  # Compare plain text passwords
                session['username'] = username
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            cursor.close()
    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Movie Upload and List
@app.route('/movies', methods=['GET', 'POST'])
def movies():
    if 'username' not in session:
        flash('Please login to access this page.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('movie')
        if file and allowed_file(file.filename):
            unique_filename = f"{random.randint(1000, 9999)}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            flash('Movie uploaded successfully!', 'success')
        else:
            flash('Invalid file type. Only MP4, MKV, AVI are allowed.', 'danger')
    movies = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('movies.html', movies=movies)

# Room Creation Route
@app.route('/create_room', methods=['POST'])
def create_room():
    if 'username' not in session:
        flash('Please login to access this feature.', 'warning')
        return redirect(url_for('login'))

    movie = request.form['movie']
    if not movie:
        flash("Please select a movie to create a room.", "danger")
        return redirect(url_for('movies'))
    room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    session['room'] = room_code
    session['movie'] = movie
    return redirect(url_for('room', room_code=room_code))

# Join Room Route
@app.route('/join_room', methods=['POST'])
def join_room_route():
    if 'username' not in session:
        flash('Please login to access this feature.', 'warning')
        return redirect(url_for('login'))

    room_code = request.form['room_code']
    movie = request.form['movie']
    if not room_code or not movie:
        flash("Room code and movie are required!", "danger")
        return redirect(url_for('movies'))
    session['room'] = room_code
    session['movie'] = movie
    return redirect(url_for('room', room_code=room_code))

# Room Route
@app.route('/room/<room_code>')
def room(room_code):
    if 'username' not in session:
        flash('Please login to access this feature.', 'warning')
        return redirect(url_for('login'))

    if 'room' not in session or session['room'] != room_code:
        flash("Invalid room code or session expired!", 'danger')
        return redirect(url_for('index'))
    movie = session.get('movie')
    return render_template('room.html', room_code=room_code, movie=movie)

# SocketIO Events
@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('message', {'user': 'System', 'msg': f'{username} has joined the room.'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    emit('message', {'user': data['user'], 'msg': data['msg']}, room=room)

@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('message', {'user': 'System', 'msg': f'{username} has left the room.'}, room=room)
# Delete Movie Route
@app.route('/delete_movie/<filename>', methods=['POST'])
def delete_movie(filename):
    if 'username' not in session:
        flash('Please login to access this feature.', 'warning')
        return redirect(url_for('login'))

    try:
        # Ensure the file exists before trying to delete
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash('Movie deleted successfully!', 'success')
        else:
            flash('Movie not found.', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('movies'))

if __name__ == '__main__':
    socketio.run(app, debug=True , port=8000)
