#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

    block = {
        "branch_data": branches,
        "prev_link": "/api/cas/"+hash_table.get("branches","")
    }
    block_data = json.dumps(block, ensure_ascii=False, sort_keys=True, indent=2)
    block_key = cas_store(block_data)
    hash_table["branches"] = block_key

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

def normalize_branch(branch_id):
    branch_id = str(branch_id)
    branch_id = re.sub(r'\s+', ' ', branch_id);
    branch_id = branch_id.strip()
    branch_id = branch_id.capitalize()
    return branch_id

def get_hash(password):
    passhash = hashlib.sha256(password.encode('utf-8'))
    return passhash.hexdigest()

# RPC API

secret_code = 'easnutm'

@app.route('/api/secret', methods=["POST"])
def handle_secret_code():
    global secret_code
    code = request.form.get('code')
    if not code:
        return "Error: query parameter 'code' was not submitted", 401
    if len(code) != len(secret_code):
        return "Access Denied: code is the wrong length", 401
    i = 0
    while i < len(secret_code):
        if code[i] != secret_code[i]:
            return "Access denied: code is incorrect at index "+str(i), 401
        i = i + 1
    if code != secret_code:
        return "Access denied: submitted code was incorrect", 401
    return "Access granted", 200



    # new_code = request.form.get('new_code')
    # if not new_code:
    #     return "Error: query parameter 'new_code' was not submitted"
    # secret_code = new_code

@app.route('/api/login', methods=["POST"])
def login():
    username = request.form['username']
    password = request.form['password']
    print([request.remote_addr, "logged in", username])
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
                total += float(account["balance"])

    return "Total: "+str(total)+" ¤"

@app.route('/api/set_password', methods=["POST"])
def set_password():
    acct = normalize(request.form['acct'])
    password = request.form['password']

    if branches["Wallet"].get(acct, None) is None:
        branches["Wallet"][acct] = {"id": acct, "balance": 0.0}

    branches["Wallet"][acct]["password"] = get_hash(password)

    update_accounts([request.remote_addr, "changed password for "+acct])
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

    update_accounts([request.remote_addr, "sent cheque", from_acct, to_acct, amount])

    return redirect('/app/', code=302)

@app.route('/api/branch_deposit', methods=["POST"])
def branch_deposit():
    account_id = session['username']
    branch_id = normalize_branch(request.form['branch_id'])
    amount = float(request.form['amount'])

    if account_id is None:
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

    update_accounts([request.remote_addr, "made a deposit", account_id, branch_id, amount])

    return redirect('/app/?branch='+branch_id, code=302)
 
@app.route('/api/branch_withdrawl', methods=["POST"])
def branch_withdrawl():
    account_id = session['username']
    branch_id = normalize_branch(request.form['branch_id'])
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
    branch_id = normalize_branch(request.args.get('branch', 'Wallet'))
    if branch_id:
        return jsonify(branches.get(branch_id, {}))
    else:
        return jsonify(accounts)

@app.route('/api/branches')
def get_branches():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    if best == 'application/json':
        return jsonify(branches)
    else:
        html = '<html><ul>'
        branch_ids = {}
        for key in branches.keys():
            branch_id = normalize_branch(key)
            branch_ids[branch_id] = True
        # branch_ids = list(branch_ids.keys()).sort()
        branch_ids = list(branch_ids.keys())
        branch_ids.sort()
        for branch_id in branch_ids:
            html += '<li><a href="/app/?branch={}">{}</a></li>'.format(branch_id,branch_id or '(none)')
        return html
 
# DHT API

hash_table = {}

@app.route('/api/dht/<path:key>', methods=["GET", "PUT"])
def dht_value(key):
    key = key.strip()
    if request.method == "PUT":
        value = str(request.data.decode("utf-8", "strict"))
        hash_table[key] = value
        if key == 'branches':
            reset_branches(value)
    if request.method == "GET":
        value = hash_table.get(key)
    with open('data/hash_table.json', 'w') as jsonfile:
        json.dump(hash_table, jsonfile, ensure_ascii=False, sort_keys=True, indent=2)
    return jsonify({"key":key, "value":value})

@app.route('/api/dht', methods=["GET"])
def dht_dump():
    return jsonify(hash_table)

def reset_branches(value):
    if value in content_table:
        global branches
        global accounts
        branch_json = content_table[value]
        branch_data = json.loads(branch_json)['branch_data']
        branches = branch_data
        accounts = branches['Wallet']
        update_accounts([request.remote_addr, "reset blockchain", value])

content_table = {}

def cas_store(value):
    key = get_hash(value)
    content_table[key] = value
    with open('data/content_table.json', 'w') as jsonfile:
        json.dump(content_table, jsonfile, ensure_ascii=False, sort_keys=True, indent=2)
    return key

@app.route('/api/cas/<path:key>', methods=["GET", "PUT"])
def cas_value(key):
    if request.method == "PUT":
        value = str(request.data.decode("utf-8", "strict"))
        cas_store(value)
        return jsonify({"key":key, "value":value})
    if request.method == "GET":
        value = content_table.get(key)
        best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
        if best == 'application/json':
            return jsonify({"key":key, "value":value})
        else:
            return linkify(str(value))

def linkify(text):
    text = re.sub(r'(/api/cas/\w*)', '<a href="\\1">\\1</a>', text)
    return text

@app.route('/api/cas/', methods=["POST"])
def cas_create():
    value = request.data.decode("utf-8", "strict")
    key = get_hash(value)
    content_table[key] = value
    return jsonify({"key": key, "value": value})

@app.route('/api/cas', methods=["GET"])
def cas_dump():
    return jsonify(content_table)

@app.route('/api/blockchain')
def get_blockchain():
    key = hash_table['branches']
    return redirect('/api/cas/'+key, 302)

@app.route('/api/reset_blockchain', methods=["POST"])
def reset_blockchain():
    global branches
    global accounts
    new_hash = request.form['hash']
    if new_hash in content_table:
        reset_branches(new_hash)
        return redirect("/app/", code=302)
    else:
        return "Error: new hash is not in content-addressed storage table"

# streaming API

@socketio.on('new_client')
def new_client(message):
    # note that session is available
    socketio.emit('accounts_data', {'accounts': accounts})
    socketio.emit('branch_data', {'branches': branches})


@socketio.on('send_message')
def post_message(message):
    socketio.emit('rcv_message', message)

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
    try:
        hash_table = json.load(open('data/hash_table.json'))
    except FileNotFoundError:
        hash_table = {}
    try:
        content_table = json.load(open('data/content_table.json'))
    except FileNotFoundError:
        content_table = {}
    socketio.run(app, host='0.0.0.0', port=int((os.environ.get("PORT", "9000"))))
