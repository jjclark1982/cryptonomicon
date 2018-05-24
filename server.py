#!/usr/bin/env python

from flask import Flask, session, request, render_template, jsonify, redirect, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
import json
import csv
import re
import hashlib
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "NOTASECRET")
CORS(app)
socketio = SocketIO(app, async_mode='gevent', logger=True)
branches = {}
accounts = {} # wallet balances

# serve static files

@app.route('/')
def home():
    return redirect('/app/', code=302)

@app.route('/app/')
@app.route('/app/<path:filename>')
def serve_static(filename='index.html'):
    return send_from_directory(app.static_folder, filename)

# utility functions

def update_accounts(transaction=None):
    socketio.emit('accounts_data', {'accounts': accounts})
    socketio.emit('branch_data', {'branches': accounts})
    with open('data/accounts.json', 'w') as jsonfile:
        json.dump(accounts, jsonfile, ensure_ascii=False, sort_keys=True, indent=2)
    with open('data/branches.json', 'w') as jsonfile:
        json.dump(branches, jsonfile, ensure_ascii=False, sort_keys=True, indent=2)
    if transaction:
        with open('data/transactions.csv', 'a') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(transaction)

def normalize(acct_id):
    acct_id = str(acct_id)
    acct_id = re.sub(r'\s+', '', acct_id);
    acct_id = re.sub(r'[^0-9a-zA-Z]', '', acct_id);
    acct_id = acct_id[:32]
    return acct_id

def get_hash(password):
    passhash = hashlib.sha256(password.encode('utf-8'))
    return passhash.hexdigest()

# RPC API

@app.route('/api/login', methods=["POST"])
def login():
    username = request.form['username']
    password = request.form['password']
    if username not in branches["Wallet"]:
        return "Error: no such user "+username

    account = branches["Wallet"][username]
    if get_hash(password) != account["password"]:
        return "Error: incorrect password"

    session['username'] = username
    print("setting username", session)
    return redirect('/app/', code=302)

@app.route('/api/logout', methods=["POST"])
def logout():
   # remove the username from the session if it is there
   session.pop('username', None)
   return redirect('/app/')

@app.route('/api/username')
def username():
    return jsonify(session.get('username', None))

@app.route('/api/reload_database', methods=["POST"])
def reload_database():
    global branches
    branches = json.load(open('data/branches.json'))
    return redirect("/app/", code=302)

@app.route('/api/total_money')
def total_money():
    username = request.args.get('username', None)

    total = 0.0
    for branch in branches.values():
        for account in branch.values():
            if username == None or account["id"] == username:
                total += account["balance"]

    return "Total: "+str(total)+" ¤"

@app.route('/api/set_password', methods=["POST"])
def set_password():
    acct = normalize(request.form['acct'])
    password = request.form['password']

    if branches["Wallet"].get(acct, None) is None:
        branches["Wallet"][acct] = {"id": acct, "balance": 0.0}

    branches["Wallet"][acct]["password"] = get_hash(password)

    update_accounts(["changed password for "+acct])
    return redirect('/app/', code=302)


@app.route('/api/cheque', methods=["POST"])
def send_cheque():
    from_acct = normalize(request.form['from_acct'])
    password = request.form['password']
    to_acct = normalize(request.form['to_acct'])
    amount = float(request.form['amount'])
    authorized = "authorized" in request.form

    if not authorized:
        return "Error: transaction was not authorized"

    if amount < 0:
        return "Error: amount was invalid"

    if branches["Wallet"].get(from_acct, None) is None:
        return "Error: account '{from_acct}' does not exist".format(**locals())

    if branches["Wallet"].get(from_acct).get('password',None) != get_hash(password):
        return "Error: password does not match".format(**locals())

    if branches["Wallet"][from_acct]['balance'] < amount:
        return "Error: account '{from_acct}' does not have sufficient balance".format(**locals())

    if branches["Wallet"].get(to_acct, None) is None:
        branches["Wallet"][to_acct] = {"id": to_acct, "balance": 0.0}

    branches["Wallet"][from_acct]['balance'] -= amount
    branches["Wallet"][to_acct]['balance'] += amount

    update_accounts([from_acct, to_acct, amount])
    # TODO: include originating IP address and authorization signature

    return redirect('/app/', code=302)

@app.route('/api/branch_deposit', methods=["POST"])
def branch_deposit():
    account_id = session['username']
    branch_id = request.form['branch_id']
    amount = float(request.form['amount'])

    if not account_id:
        return "Error: you must be logged in"

    if amount < 0:
        return "Error: amount was invalid"

    if branches["Wallet"].get(account_id, None) is None:
        return "Error: account '{account_id}' does not exist".format(**locals())

    if branches["Wallet"][account_id]['balance'] < amount:
        return "Error: account '{account_id}' does not have sufficient balance".format(**locals())

    if branch_id not in branches:
        branches[branch_id] = {}

    if account_id not in branches[branch_id]:
        branches[branch_id][account_id] = {"id": account_id, "balance": 0.0}

    branches["Wallet"][account_id]["balance"] -= amount    
    branches[branch_id][account_id]["balance"] += amount    

    return redirect('/app/?branch='+branch_id, code=302)
 
@app.route('/api/branch_withdrawl', methods=["POST"])
def branch_withdrawl():
    account_id = session['username']
    branch_id = request.form['branch_id']
    amount = float(request.form['amount'])

    if not account_id:
        return "Error: you must be logged in"

    if amount < 0:
        return "Error: amount was invalid"

    if branch_id not in branches:
        branches[branch_id] = {}

    if account_id not in branches[branch_id]:
        branches[branch_id][account_id] = {"id": account_id, "balance": 0.0}

    if branches[branch_id][account_id]["balance"] < amount:
        return "Error: insufficient balance in branch"

    branches[branch_id][account_id]["balance"] -= amount    
    branches["Wallet"][account_id]["balance"] += amount    

    return redirect('/app/?branch='+branch_id, code=302)


@app.route('/api/accounts')
def get_accounts():
    branch_id = request.args.get('branch', 'Wallet')
    if branch_id:
        return jsonify(branches.get(branch_id, {}))
    else:
        return jsonify(accounts)

@app.route('/api/branches')
def get_branches():
    return jsonify(branches)
 
# streaming API

@socketio.on('new_client')
def new_client(message):
    # note that session is available
    socketio.emit('accounts_data', {'accounts': accounts})
    socketio.emit('branch_data', {'branches': branches})


@socketio.on('send_message')
def post_message(message):
    socketio.emit('rcv_message', message)

True

# main routine

if __name__ == '__main__':
    import os
    try:
        accounts = json.load(open('data/accounts.json'))
    except FileNotFoundError:
        accounts = {"0": 1000000.0}
    try:
        branches = json.load(open('data/branches.json'))
    except FileNotFoundError:
        branches = {"Wallet": accounts}
    socketio.run(app, host='0.0.0.0', port=int((os.environ.get("PORT", "9000"))))

print(accounts)
