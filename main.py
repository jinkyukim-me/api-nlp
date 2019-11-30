from flask import Flask, render_template, request, redirect, url_for, session, make_response
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
import MySQLdb.cursors
import re
import uuid
import hashlib
import datetime

app = Flask(__name__)

app.secret_key = 'seocho'

app.config['threaded'] = True

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'kaist30#'
app.config['MYSQL_DB'] = 'pythonlogin'

app.config['MAIL_SERVER']= 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your password'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mysql = MySQL(app)

mail = Mail(app)

account_activation_required = False

@app.route('/pythonlogin/', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        # Get the hashed password
        hash = password + app.secret_key
        hash = hashlib.sha1(hash.encode())
        password = hash.hexdigest();
        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = %s AND password = %s', (username, password))
        # Fetch one record and return result
        account = cursor.fetchone()
        # If account exists in accounts table in out database
        if account:
            # Create session data, we can access this data in other routes
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            if 'rememberme' in request.form:
                # Create hash to store as cookie
                hash = account['username'] + request.form['password'] + app.secret_key
                hash = hashlib.sha1(hash.encode())
                hash = hash.hexdigest();
                # the cookie expires in 90 days
                expire_date = datetime.datetime.now() + datetime.timedelta(days=90)
                resp = make_response('Success', 200)
                resp.set_cookie('rememberme', hash, expires=expire_date)
                # Update rememberme in accounts table to the cookie hash
                cursor.execute('UPDATE accounts SET rememberme = %s WHERE id = %s', (hash, account['id']))
                mysql.connection.commit()
                return resp
            return 'Success'
        else:
            # Account doesnt exist or username/password incorrect
            return 'Incorrect username/password!'
    # Show the login form with message (if any)
    return render_template('index.html', msg=msg)

# http://localhost:5000/pythinlogin/register - this will be the registration page, we need to use both GET and POST requests
@app.route('/pythonlogin/register', methods=['GET', 'POST'])
def register():
    # Output message if something goes wrong...
    msg = ''
    # Check if "username", "password" and "email" POST requests exist (user submitted form)
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        # Create variables for easy access
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        # Hash the password
        hash = password + app.secret_key
        hash = hashlib.sha1(hash.encode())
        password = hash.hexdigest();
        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
        account = cursor.fetchone()
        # If account exists show error and validation checks
        if account:
            return 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            return 'Invalid email address!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            return 'Username must contain only characters and numbers!'
        elif not username or not password or not email:
            return 'Please fill out the form!'
        elif account_activation_required:
            # Account activation enabled
            # Generate a random unique id for activation code
            activation_code = uuid.uuid4()
            cursor.execute('INSERT INTO accounts VALUES (NULL, %s, %s, %s, %s, "")', (username, password, email, activation_code))
            mysql.connection.commit()
            # Change your_email@gmail.com
            email = Message('Account Activation Required', sender = 'your_email@gmail.com', recipients = [email])
            # change yourdomain.com to your website, to test locally you can go to: http://localhost:5000/pythonlogin/activate/<email>/<code>
            activate_link = 'http://yourdomain.com/pythonlogin/activate/' + str(email) + '/' + str(activation_code)
            # change the email body below
            email.body = '<p>Please click the following link to activate your account: <a href="' + str(activate_link) + '">' + str(activate_link) + '</a></p>'
            mail.send(email)
            return 'Please check your email to activate your account!'
        else:
            # Account doesnt exists and the form data is valid, now insert new account into accounts table
            cursor.execute('INSERT INTO accounts VALUES (NULL, %s, %s, %s, "", "")', (username, password, email))
            mysql.connection.commit()
            return 'You have successfully registered!'
    elif request.method == 'POST':
        # Form is empty... (no POST data)
        return 'Please fill out the form!'
    # Show registration form with message (if any)
    return render_template('register.html', msg=msg)

# http://localhost:5000/pythinlogin/activate/<email>/<code> - this page will activate a users account if the correct activation code and email are provided
@app.route('/pythonlogin/activate/<string:email>/<string:code>', methods=['GET'])
def activate(email, code):
    # Check if the email and code provided exist in the accounts table
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM accounts WHERE email = %s AND activation_code = %s', (email, code))
    account = cursor.fetchone()
    if account:
        # account exists, update the activation code to "activated"
        cursor.execute('UPDATE accounts SET activation_code = "activated" WHERE email = %s AND activation_code = %s', (email, code))
        mysql.connection.commit()
        # print message, or you could redirect to the login page...
        return 'Account Activated!'
    return 'Account doesn\'t exist with that email or incorrect activation code!'

# http://localhost:5000/pythinlogin/home - this will be the home page, only accessible for loggedin users
@app.route('/pythonlogin/home')
def home():
    # Check if user is loggedin
    if loggedin():
        # User is loggedin show them the home page
        return render_template('home.html', username=session['username'])
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))

# http://localhost:5000/pythinlogin/profile - this will be the profile page, only accessible for loggedin users
@app.route('/pythonlogin/profile')
def profile():
    # Check if user is loggedin
    if loggedin():
        # We need all the account info for the user so we can display it on the profile page
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE id = %s', (session['id'],))
        account = cursor.fetchone()
        # Show the profile page with account info
        return render_template('profile.html', account=account)
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))

@app.route('/pythonlogin/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    # Check if user is loggedin
    if loggedin():
        # We need all the account info for the user so we can display it on the profile page
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Output message
        msg = ''
        # Check if "username", "password" and "email" POST requests exist (user submitted form)
        if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
            # Create variables for easy access
            username = request.form['username']
            password = request.form['password']
            email = request.form['email']
            # Hash the password
            hash = password + app.secret_key
            hash = hashlib.sha1(hash.encode())
            password = hash.hexdigest();
            # update account with the new details
            cursor.execute('UPDATE accounts SET username = %s, password = %s, email = %s WHERE id = %s', (username, password, email, session['id']))
            mysql.connection.commit()
            msg = 'Updated!'
        cursor.execute('SELECT * FROM accounts WHERE id = %s', (session['id'],))
        account = cursor.fetchone()
        # Show the profile page with account info
        return render_template('profile-edit.html', account=account, msg=msg)
    return redirect(url_for('login'))

# http://localhost:5000/pythinlogin/logout - this will be the logout page
@app.route('/pythonlogin/logout')
def logout():
    # Remove session data, this will log the user out
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    # Remove cookie data "remember me"
    resp = make_response(redirect(url_for('login')))
    resp.set_cookie('rememberme', expires=0)
    return resp

# Check if logged in function, update session if cookie for "remember me" exists
def loggedin():
    if 'loggedin' in session:
        return True;
    elif 'rememberme' in request.cookies:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # check if remembered, cookie has to match the "rememberme" field
        cursor.execute('SELECT * FROM accounts WHERE rememberme = %s', (request.cookies['rememberme'],))
        account = cursor.fetchone()
        if account:
            # update session variables
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return True
    # account not logged in return false
    return False

if __name__ == '__main__':
    app.run()
