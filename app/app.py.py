from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Create DB
def init_db():
    conn = sqlite3.connect('food.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_type TEXT,
            quantity TEXT,
            location TEXT,
            contact TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    if request.method == 'POST':
        food_type = request.form['food_type']
        quantity = request.form['quantity']
        location = request.form['location']
        contact = request.form['contact']

        conn = sqlite3.connect('food.db')
        c = conn.cursor()
        c.execute("INSERT INTO donations VALUES (NULL,?,?,?,?,?)",
                  (food_type, quantity, location, contact, 'Available'))
        conn.commit()
        conn.close()

        return redirect('/ngo')
    return render_template('donate.html')

@app.route('/ngo')
def ngo():
    conn = sqlite3.connect('food.db')
    c = conn.cursor()
    c.execute("SELECT * FROM donations WHERE status='Available'")
    donations = c.fetchall()
    conn.close()
    return render_template('ngo.html', donations=donations)

@app.route('/accept/<int:id>')
def accept(id):
    conn = sqlite3.connect('food.db')
    c = conn.cursor()
    c.execute("UPDATE donations SET status='Accepted' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/ngo')

if __name__ == '__main__':
    app.run(debug=True)
