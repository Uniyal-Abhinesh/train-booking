from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Cobrakai@123'
app.config['MYSQL_DB'] = 'train'

mysql = MySQL(app)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                flash('Username already exists! Choose another.')
                cur.close()
                return redirect(url_for('register'))

            cur.execute(
                "INSERT INTO users (username, password, email, phone) VALUES (%s, %s, %s, %s)",
                (username, password, email, phone)
            )
            mysql.connection.commit()
            cur.close()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))

        except Exception:
            flash('An error occurred while registering. Please try again.')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = cur.fetchone()
            cur.close()

            if user:
                # Redirect to dashboard passing username in query params
                return redirect(url_for('dashboard', username=username))
            else:
                flash('Invalid username or password.')
                return redirect(url_for('login'))

        except Exception:
            flash('An error occurred during login. Please try again.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    username = request.args.get('username')
    if not username:
        flash('Please log in first.')
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=username)

@app.route('/book', methods=['POST'])
def book_ticket():
    username = request.form.get('username')
    if not username:
        flash('Please log in first.')
        return redirect(url_for('login'))

    name = request.form['name']
    source = request.form['source']
    destination = request.form['destination']
    train = request.form['train']
    date = request.form['date']

    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO tickets (username, name, source, destination, train, date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, name, source, destination, train, date))
        mysql.connection.commit()
        cur.close()
        flash('Ticket booked successfully!')
        return redirect(url_for('dashboard', username=username))

    except Exception:
        flash('An error occurred while booking the ticket. Please try again.')
        return redirect(url_for('dashboard', username=username))

@app.route('/logout')
def logout():
    flash('Logged out successfully.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
