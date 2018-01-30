# -*- coding: utf-8 -*-
"""
    MiniTwit
    ~~~~~~~~

    A microblogging application written with Flask and sqlite3.

    :copyright: (c) 2015 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

import time
#from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from datetime import datetime
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from werkzeug import check_password_hash, generate_password_hash
import MySQLdb

db = MySQLdb.connect(host="minitwitdb.ckqykakd7kf7.us-west-2.rds.amazonaws.com", user="weaverm1",passwd="Coswin17!", db="miniTwitDB",port=5000)
cur = db.cursor()
print("sanity cheq")
# configuration
DATABASE = db
PER_PAGE = 30
DEBUG = True
SECRET_KEY = b'_5#y2L"F4Q8z\n\xec]/'

# create our little application :)
app = Flask('minitwit')
app.config.from_object(__name__)
app.config.from_envvar('MINITWIT_SETTINGS', silent=True)


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    top = _app_ctx_stack.top 
    if not hasattr(top, 'miniTwitDB'):
        top.mysql_db = MySQLdb.connect(host="minitwitdb.ckqykakd7kf7.us-west-2.rds.amazonaws.com", user="weaverm1",passwd="Coswin17!", db="miniTwitDB",port=5000)
   # for row in cur.fetchall():
    #    print row[0]    
   # top.mysql_db.row_factory = MySQLdb.Row
    return top.mysql_db.cursor()


@app.teardown_appcontext
def close_database(exception):
    """Closes the database again at the end of the request."""
    top = _app_ctx_stack.top
    if hasattr(top, 'mysql_db'):
        top.mysql_db.close()


def init_db():
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Creates the database tables."""
    init_db()
    print('Initialized the database.')


def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    print(query)
    print("ARGS:")
    for i in args:
        print(i)
    cur = get_db()
    num  = cur.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def get_user_id(username):
    """Convenience method to look up the id for a username."""
    rv = query_db("SELECT user_id FROM user WHERE username =%s",
                  (username,), one=True)
    return rv[0] if rv else None


def format_datetime(timestamp):
    """Format a timestamp for display."""
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d @ %H:%M')


def gravatar_url(email, size=80):
    """Return the gravatar image for the given email address."""
    return 'https://www.gravatar.com/avatar/%s%sd=identicon&s=%d' % \
        (md5(email.strip().lower().encode('utf-8')).hexdigest(), size)


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        print("USER_ID:")
        print(session['user_id'])
        g.user = query_db("SELECT * FROM user WHERE user_id = %s",
                          (session['user_id'],), one=True)


@app.route('/')
def timeline():
    """Shows a users timeline or if no user is logged in it will
    redirect to the public timeline.  This timeline shows the user's
    messages as well as all the messages of followed users.
    """
    if not g.user:
        return redirect(url_for('public_timeline'))
    return render_template('timeline.html', messages=query_db('''
        SELECT message.*, user.* FROM message, user
        WHERE message.author_id = user.user_id AND (
            user.user_id = %s OR
            user.user_id IN (SELECT whom_id FROM follower
                                    WHERE who_id = %s))
        ORDER BY message.pub_date DESC LIMIT %s''',
        [session['user_id'], session['user_id'], PER_PAGE]))


@app.route('/public')
def public_timeline():
    """Displays the latest messages of all users."""
    return render_template('timeline.html', messages=query_db('''
        SELECT message.*, user.* FROM message, user
        WHERE message.author_id = user.user_id
        ORDER BY message.pub_date DESC LIMIT %s''', ([PER_PAGE])))


@app.route('/<username>')
def user_timeline(username):
    """Display's a users tweets."""
    print(username)
    print("is USERNAME")
    profile_user = query_db("SELECT * FROM user WHERE username = %s",
                            (username,), one=True)
    if profile_user is None:
        abort(404)
    followed = False
    if g.user:
        followed = query_db('''SELECT 1 FROM follower WHERE
            follower.who_id = %s AND follower.whom_id = %s''',
            ([session['user_id'], profile_user['user_id']]),
            one=True) is not None
    return render_template('timeline.html', messages=query_db('''
            SELECT message.*, user.* FROM message, user WHERE
            user.user_id = message.author_id AND user.user_id = %s
            ORDER BY message.pub_date DESC LIMIT %s''',
            ([profile_user['user_id'], PER_PAGE])), followed=followed,
            profile_user=profile_user)


@app.route('/<username>/follow')
def follow_user(username):
    """Adds the current user as follower of the given user."""
    if not g.user:
        abort(401)
    whom_id = get_user_id(username)
    if whom_id is None:
        abort(404)
    db = get_db()
    db.execute('INSERT INTO follower (who_id, whom_id) VALUES (%s, %s)',
              ([session['user_id'], whom_id]))
    db.commit()
    flash('You are now following "%s"' % username)
    return redirect(url_for('user_timeline', username=username))


@app.route('/<username>/unfollow')
def unfollow_user(username):
    """Removes the current user as follower of the given user."""
    if not g.user:
        abort(401)
    whom_id = get_user_id(username)
    if whom_id is None:
        abort(404)
    db = get_db()
    db.execute('DELETE FROM follower WHERE who_id=%s AND whom_id=%s',
              ([session['user_id'], whom_id]))
    db.commit()
    flash('You are no longer following "%s"' % username)
    return redirect(url_for('user_timeline', username=username))


@app.route('/add_message', methods=['POST'])
def add_message():
    """Registers a new message for the user."""
    if 'user_id' not in session:
        abort(401)
    if request.form['text']:
        db = get_db()
        db.execute('''INSERT INTO message (author_id, text, pub_date)
          VALUES (%s, %s, %s)''', ((session['user_id'], request.form['text'],
                                int(time.time()))))
        db.commit()
        flash('Your message was recorded')
    return redirect(url_for('timeline'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Logs the user in."""
    if g.user:
        return redirect(url_for('timeline'))
    error = None
    if request.method == 'POST':
        print(request.form['username'])
        print('DEBUG: TESTING USERNAME')
        user = query_db('''SELECT * FROM user WHERE
            username = %s''', (request.form['username'],), one=True) 
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['pw_hash'],
                                     request.form['password']):
            error = 'Invalid password'
        else:
            flash('You were logged in')
            session['user_id'] = user['user_id']
            return redirect(url_for('timeline'))
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registers the user."""
    if g.user:
        return redirect(url_for('timeline'))
    error = None
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['email'] or \
                '@' not in request.form['email']:
            error = 'You have to enter a valid email address'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif get_user_id(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            cur = get_db()
            cur.execute('''INSERT INTO user (
              username, email, pw_hash) VALUES (%s, %s, %s)''',
              ([request.form['username'], request.form['email'],
               generate_password_hash(request.form['password'])]))
            db.commit()
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    """Logs the user out."""
    flash('You were logged out')
    session.pop('user_id', None)
    return redirect(url_for('public_timeline'))


# add some filters to jinja
app.jinja_env.filters['datetimeformat'] = format_datetime
app.jinja_env.filters['gravatar'] = gravatar_url
