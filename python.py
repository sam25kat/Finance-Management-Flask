














from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import openai
import matplotlib
import io
import base64
matplotlib.use('Agg')  # Use the 'Agg' backend for rendering plots
import matplotlib.pyplot as plt
from datetime import datetime
from datetime import datetime, timedelta
import pyttsx3


app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SECRET_KEY'] = "this is my key!"
#openai.api_key = ''


# Configure database connection
app.config['MYSQL_HOST'] = 
app.config['MYSQL_USER'] = 
app.config['MYSQL_PASSWORD'] = 
app.config['MYSQL_DB'] = 

def get_db_connection():
    return pymysql.connect(host=app.config['MYSQL_HOST'],
                           user=app.config['MYSQL_USER'],
                           password=app.config['MYSQL_PASSWORD'],
                           db=app.config['MYSQL_DB'])
    
def speak(text):
    engine = pyttsx3.init()
    rate = engine.getProperty('rate')                       
    engine.setProperty('rate', 120)
    voices = engine.getProperty('voices')       
    engine.setProperty('voice', voices[1].id)
    engine.say(text)
    print('jarvis: ',text)
    engine.runAndWait()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST': 
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1].upper()
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (first_name, last_name, email, password_hash) VALUES (%s, %s, %s, %s)',
                           (firstname, lastname, email, password_hash))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
        except pymysql.MySQLError as e:
            flash(f'Error: {e.args[1]}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('index'))
    return render_template('index.html')

@app.route('/add_money', methods=['GET', 'POST'])
def add_money():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        amount = float(request.form['amount'])
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if the user has an existing balance entry
            cursor.execute('SELECT * FROM user_balance WHERE user_id = %s', (session['user_id'],))
            balance_entry = cursor.fetchone()
            
            if balance_entry:
                # Update the existing balance
                cursor.execute('UPDATE user_balance SET balance = balance + %s WHERE user_id = %s', (amount, session['user_id']))
            else:
                # Insert a new balance entry
                cursor.execute('INSERT INTO user_balance (user_id, balance) VALUES (%s, %s)', (session['user_id'], amount))
            
            conn.commit()
            # Insert into add_money table
            cursor.execute('INSERT INTO add_money (user_id, amount) VALUES (%s, %s)', (session['user_id'], amount))
            conn.commit()
            # Insert into transaction table with local timestamp
            local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO transaction (user_id, transaction_type, amount, timestamp) VALUES (%s, %s, %s, %s)', 
                           (session['user_id'], 'add_money', amount, local_time))
            conn.commit()
            flash('Money added successfully!', 'success')
        except pymysql.MySQLError as e:
            flash(f'Error: {e.args[1]}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('dashboard'))
    return render_template('add_money.html', user_name=session['user_name'])

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        spent_amount = float(request.form['spent_amount'])
        reason = request.form['reason']
        category = request.form['category']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Start a transaction
            conn.begin()
            
            # Check current balance from user_balance table
            cursor.execute('SELECT balance FROM user_balance WHERE user_id = %s', (session['user_id'],))
            current_balance_entry = cursor.fetchone()

            if current_balance_entry:
                current_balance = current_balance_entry[0]
                if current_balance < spent_amount:
                    flash('Insufficient balance!', 'danger')
                    conn.rollback()
                    return redirect(url_for('add_expense'))
                
                # Update the balance
                cursor.execute('UPDATE user_balance SET balance = balance - %s WHERE user_id = %s', (spent_amount, session['user_id']))
                
                # Insert the expense record
                cursor.execute('INSERT INTO expense (user_id, spent_amount, reason, category) VALUES (%s, %s, %s, %s)',
                               (session['user_id'], spent_amount, reason, category))
                
                # Insert into transaction table with local timestamp
                local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('INSERT INTO transaction (user_id, transaction_type, amount, timestamp) VALUES (%s, %s, %s, %s)', 
                               (session['user_id'], 'expense', spent_amount, local_time))
                
                # Commit the transaction
                conn.commit()
                flash('Expense added successfully!', 'success')
            else:
                flash('No balance record found for user.', 'danger')
                conn.rollback()
                return redirect(url_for('add_expense'))
                
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'Error: {e.args[1]}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('dashboard'))
    
    return render_template('add_expense.html',user_name=session['user_name'])

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the balance
    cursor.execute('SELECT balance FROM user_balance WHERE user_id = %s', (session['user_id'],))
    balance_entry = cursor.fetchone()
    balance = balance_entry[0] if balance_entry else 0
    
    # Get the last 10 transactions
    cursor.execute('''
        SELECT 
            t.transaction_type, 
            t.amount, 
            t.timestamp, 
            IF(t.transaction_type = 'expense', e.reason, NULL) AS reason
        FROM 
            transaction t
        LEFT JOIN 
            expense e ON t.user_id = e.user_id AND t.amount = e.spent_amount AND t.transaction_type = 'expense'
        WHERE 
            t.user_id = %s
        ORDER BY 
            t.timestamp DESC 
        LIMIT 5
    ''', (session['user_id'],))
    transactions = cursor.fetchall()

    # Calculate total owed to the user
    cursor.execute('SELECT SUM(amount) FROM loans WHERE receiver_id = %s', (session['user_id'],))
    total_owed_entry = cursor.fetchone()
    total_owed = total_owed_entry[0] if total_owed_entry[0] is not None else 0

    # Calculate total owed by the user
    cursor.execute('SELECT SUM(amount) FROM loans WHERE borrower_id = %s', (session['user_id'],))
    total_owe_entry = cursor.fetchone()
    total_owe = total_owe_entry[0] if total_owe_entry[0] is not None else 0
    

    cursor.close()
    conn.close()

    return render_template('dashboard.html', 
                           user_name=session['user_name'], 
                           balance=balance, 
                           transactions=transactions,
                           total_owed=total_owed,
                           total_owe=total_owe)


@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute('''
        SELECT 
            t.transaction_type, 
            t.amount, 
            t.timestamp, 
            IF(t.transaction_type = 'expense', e.reason, NULL) AS reason
        FROM 
            transaction t
        LEFT JOIN 
            expense e ON t.user_id = e.user_id AND t.amount = e.spent_amount AND t.transaction_type = 'expense'
        WHERE 
            t.user_id = %s
        ORDER BY 
            t.timestamp DESC
    ''', (session['user_id'],))
    transactions = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('transaction.html', user_name=session['user_name'], transactions=transactions)


@app.route('/about')
def about():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))
    return render_template('about.html', user_name=session['user_name'])

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))






@app.route('/borrow', methods=['GET', 'POST'])
def borrow():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        receiver_email = request.form['receiver_email']
        amount = float(request.form['amount'])
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Get the receiver's user_id from the email
            cursor.execute('SELECT user_id FROM users WHERE email = %s', (receiver_email,))
            receiver = cursor.fetchone()
            if receiver:
                receiver_id = receiver[0]
                borrower_id = session['user_id']
                cursor.execute('INSERT INTO requests (borrower_id, receiver_id, amount) VALUES (%s, %s, %s)', 
                               (borrower_id, receiver_id, amount))
                conn.commit()
                flash('Borrow request sent successfully!', 'success')
            else:
                flash('Receiver not found!', 'danger')
        except pymysql.MySQLError as e:
            flash(f'Error: {e.args[1]}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('dashboard'))
    return render_template('borrow.html',user_name=session['user_name'])

@app.route('/requests', methods=['GET', 'POST'])
def requests_page():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        request_id = request.form['request_id']
        action = request.form['action']
        cursor.execute('SELECT * FROM requests WHERE id = %s', (request_id,))
        req = cursor.fetchone()
        if req and req[4] == 'pending':
            borrower_id = req[1]
            receiver_id = req[2]
            amount = req[3]
            if action == 'approve':
                try:
                    # Update request status to 'approved'
                    cursor.execute('UPDATE requests SET status = %s WHERE id = %s', ('approved', request_id))
                    
                    # Insert into loans table
                    cursor.execute('INSERT INTO loans (borrower_id, receiver_id, amount) VALUES (%s, %s, %s)', 
                                   (borrower_id, receiver_id, amount))
                    
                    # Update user balance
                    cursor.execute('UPDATE user_balance SET balance = balance - %s WHERE user_id = %s', 
                                   (amount, receiver_id))
                    cursor.execute('UPDATE user_balance SET balance = balance + %s WHERE user_id = %s', 
                                   (amount, borrower_id))
                    
                    # Record the transaction
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('INSERT INTO transaction (user_id, transaction_type, amount, timestamp) VALUES (%s, %s, %s, %s)', 
                                   (receiver_id, 'loan', -amount, timestamp))
                    cursor.execute('INSERT INTO transaction (user_id, transaction_type, amount, timestamp) VALUES (%s, %s, %s, %s)', 
                                   (borrower_id, 'loan', amount, timestamp))
                    
                    conn.commit()
                    flash('Request approved!', 'success')
                except pymysql.MySQLError as e:
                    conn.rollback()
                    flash(f'Error: {e.args[1]}', 'danger')
            elif action == 'reject':
                try:
                    # Update request status to 'rejected'
                    cursor.execute('UPDATE requests SET status = %s WHERE id = %s', ('rejected', request_id))
                    conn.commit()
                    flash('Request rejected!', 'success')
                except pymysql.MySQLError as e:
                    conn.rollback()
                    flash(f'Error: {e.args[1]}', 'danger')
        else:
            flash('Request not found or already processed.', 'danger')
    
    cursor.execute('SELECT r.id, u1.first_name, u1.last_name, r.amount, r.status, r.created_at FROM requests r JOIN users u1 ON r.borrower_id = u1.user_id WHERE r.receiver_id = %s AND r.status = %s', (session['user_id'], 'pending'))
    requests = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('requests.html', user_name=session['user_name'], requests=requests)



@app.route('/settle_debt', methods=['GET', 'POST'])
def settle_debt():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT u.user_id, u.first_name, u.last_name, SUM(l.amount) as amount_owed
        FROM loans l
        JOIN users u ON l.receiver_id = u.user_id
        WHERE l.borrower_id = %s
        GROUP BY u.user_id, u.first_name, u.last_name
    ''', (session['user_id'],))
    users_owed = cursor.fetchall()
    print("Users Owed:", users_owed)  # Debugging line

    cursor.execute('''
        SELECT u.user_id, u.first_name, u.last_name, SUM(l.amount) as amount_owed
        FROM loans l
        JOIN users u ON l.borrower_id = u.user_id
        WHERE l.receiver_id = %s
        GROUP BY u.user_id, u.first_name, u.last_name
    ''', (session['user_id'],))
    users_owes = cursor.fetchall()
    print("Users Owes:", users_owes)  # Debugging line

    if request.method == 'POST':
        selected_user_id = request.form['user_id']
        amount = float(request.form['amount'])
        settle_type = request.form['settle_type']

        try:
            if settle_type == 'owed':
                cursor.execute('UPDATE loans SET amount = amount - %s WHERE receiver_id = %s AND borrower_id = %s AND amount >= %s', 
                               (amount, selected_user_id, session['user_id'], amount))
                cursor.execute('UPDATE user_balance SET balance = balance + %s WHERE user_id = %s', 
                               (amount, selected_user_id))
                cursor.execute('UPDATE user_balance SET balance = balance - %s WHERE user_id = %s', 
                               (amount, session['user_id']))
                # Log the transaction
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO transaction (user_id, amount, transaction_type, timestamp)
                    VALUES (%s, %s, %s, %s)
                ''', (session['user_id'], -amount, 'settle', timestamp))
                cursor.execute('''
                    INSERT INTO transaction (user_id, amount, transaction_type, timestamp)
                    VALUES (%s, %s, %s, %s)
                ''', (selected_user_id, amount, 'settle', timestamp))
            elif settle_type == 'owes':
                cursor.execute('UPDATE loans SET amount = amount - %s WHERE borrower_id = %s AND receiver_id = %s AND amount >= %s', 
                               (amount, selected_user_id, session['user_id'], amount))
                
                cursor.execute('UPDATE user_balance SET balance = balance - %s WHERE user_id = %s', 
                               (amount, selected_user_id))
                cursor.execute('UPDATE user_balance SET balance = balance + %s WHERE user_id = %s', 
                               (amount, session['user_id']))
                # Log the transaction
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO transaction (user_id, amount, transaction_type, timestamp)
                    VALUES (%s, %s, %s, %s)
                ''', (session['user_id'], amount, 'settle', timestamp))
                cursor.execute('''
                    INSERT INTO transaction (user_id, amount, transaction_type, timestamp)
                    VALUES (%s, %s, %s, %s)
                ''', (selected_user_id, -amount, 'settle', timestamp))

            conn.commit()
            flash('Debt settled successfully!', 'success')
        except pymysql.MySQLError as e:
            flash(f'Error: {e.args[1]}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('dashboard'))

    cursor.close()
    conn.close()

    return render_template('settle_debt.html', users_owed=users_owed, users_owes=users_owes,user_id=session['user_id'],user_name=session['user_name'])





@app.route('/chat')
def chat():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, CONCAT(first_name, " ", last_name) AS name FROM users WHERE user_id != %s', (session['user_id'],))
    all_users = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('chat.html', all_users=all_users,user_name=session['user_name'])

@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
def chat_with_user(user_id):
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        message = request.form['message']
        sender_id = session['user_id']
        receiver_id = user_id
        timestamp = datetime.now()
        cursor.execute('INSERT INTO chat (sender_id, receiver_id, message, timestamp) VALUES (%s, %s, %s, %s)', (sender_id, receiver_id, message, timestamp))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('chat_with_user', user_id=user_id))  # Redirect after POST

    cursor.execute('''
        SELECT u.first_name, c.message, c.sender_id 
        FROM chat c 
        JOIN users u ON c.sender_id = u.user_id 
        WHERE (c.sender_id = %s AND c.receiver_id = %s) OR (c.sender_id = %s AND c.receiver_id = %s) 
        ORDER BY c.timestamp
    ''', (session['user_id'], user_id, user_id, session['user_id']))
    messages = cursor.fetchall()

    cursor.execute('SELECT CONCAT(first_name, " ", last_name) AS name FROM users WHERE user_id = %s', (user_id,))
    receiver_name = cursor.fetchone()[0]
    cursor.execute('SELECT CONCAT(first_name, " ", last_name) AS name FROM users WHERE user_id = %s', (session['user_id'],))
    user_name = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return render_template('chat_with_user.html', receiver_id=user_id, receiver_name=receiver_name, user_name=session['user_name'], messages=messages)


@app.route('/gpt', methods=['GET', 'POST'])
def gpt():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    suggestions = None
    if request.method == 'POST':
        user_prompt = request.form['prompt']
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch transactions
        cursor.execute('SELECT transaction_type, amount, timestamp FROM transaction WHERE user_id = %s', (session['user_id'],))
        transactions = cursor.fetchall()

        # Fetch expenses
        cursor.execute('SELECT reason, spent_amount, category, timestamp FROM expense WHERE user_id = %s', (session['user_id'],))
        expenses = cursor.fetchall()

        # Fetch balance
        cursor.execute('SELECT balance FROM user_balance WHERE user_id = %s', (session['user_id'],))
        balance = cursor.fetchone()

        cursor.close()
        conn.close()

        # Prepare transaction data
        transaction_data = "\n".join([f"{t[0]}: {t[1]} on {t[2]}" for t in transactions])
        expense_data = "\n".join([f"{e[0]}: {e[1]} on {e[3]} ({e[2]})" for e in expenses])
        balance_info = f"Current balance: {balance[0]}"

        prompt = f"Here are the recent transactions: \n{transaction_data}\n\nHere are the recent expenses: \n{expense_data}\n\n{balance_info}\n\nUser prompt: {user_prompt}"

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-16k",
                messages=[
                    {"role": "system", "content": "You are a financial assistant."},
                    {"role": "user", "content": prompt}
                ]
            )

            suggestions = response.choices[0].message['content']
        except openai.error.RateLimitError:
            flash('You have exceeded your current quota. Please check your plan and billing details.', 'danger')
        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')

    return render_template('gpt.html', suggestions=suggestions, user_name=session['user_name'])


@app.route('/insights', methods=['GET', 'POST'])
def insights():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('index'))

    user_id = session['user_id']
    period = request.args.get('period', 'all')

    conn = get_db_connection()
    cursor = conn.cursor()

    if period == 'today':
        start_date = datetime.now().date()
    elif period == 'week':
        start_date = datetime.now() - timedelta(days=datetime.now().weekday())
    elif period == 'onth':
        start_date = datetime(datetime.now().year, datetime.now().month, 1)
    else:
        start_date = datetime(1970, 1, 1)

    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')

    categories = ['grocery', 'bill', 'entertainment', 'food', 'other']
    amounts = {}

    for category in categories:
        cursor.execute('''
            SELECT 
                SUM(e.spent_amount) AS total_amount
            FROM 
                expense e
            WHERE 
                e.user_id = %s AND e.category = %s AND e.timestamp >= %s
        ''', (user_id, category, start_date_str))

        result = cursor.fetchone()
        if result[0] is not None:
            amounts[category] = float(result[0])
        else:
            amounts[category] = 0.0

    conn.close()

    if not any(amounts.values()):
        flash('No transactions found for the selected period.', 'warning')
        return render_template('insights.html', user_name=session['user_name'], plot_url=None, text={})

    # Generate pie chart
    categories = list(amounts.keys())
    values = list(amounts.values())

    fig, ax = plt.subplots()
    ax.pie(values, labels=categories, autopct='%1.1f%%', startangle=90, pctdistance=0.65, labeldistance=1.1)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle. # Equal aspect ratio ensures that pie is drawn as a circle.

    # Save the plot to a BytesIO object and encode it in base64
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)
    return render_template('insights.html', user_name=session['user_name'], plot_url=plot_url, text=amounts)
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')