#!/usr/bin/env python

from flask import Flask, request, render_template, jsonify, redirect, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
import json
import csv
import re
import hashlib

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, async_mode='gevent', logger=True)
accounts = {}
jobs = {}

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
    global accounts
    socketio.emit('accounts_data', {'accounts': accounts})
    with open('data/accounts.json', 'w') as jsonfile:
        json.dump(accounts, jsonfile, ensure_ascii=False, sort_keys=True, indent=2)
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

# REST API

@app.route('/api/set_password', methods=["POST"])
def set_password():
    global accounts
    acct = normalize(request.form['acct'])
    password = request.form['password']

    if accounts.get(acct, None) is None:
        accounts[acct] = {"id": acct, "balance": 0.0}

    accounts[acct]["password"] = get_hash(password)

    update_accounts([])
    return redirect('/app/', code=302)


@app.route('/api/cheque', methods=["POST"])
def send_cheque():
    global accounts
    from_acct = normalize(request.form['from_acct'])
    password = request.form['password']
    to_acct = normalize(request.form['to_acct'])
    amount = float(request.form['amount'])
    authorized = "authorized" in request.form

    if not authorized:
        return "Error: transaction was not authorized"

    if amount < 0:
        return "Error: amount was invalid"

    if accounts.get(from_acct, None) is None:
        return "Error: account '{from_acct}' does not exist".format(**locals())

    if accounts.get(from_acct).get('password',None) != get_hash(password):
        return "Error: password does not match".format(**locals())

    if accounts[from_acct]['balance'] < amount:
        return "Error: account '{from_acct}' does not have sufficient balance".format(**locals())

    if accounts.get(to_acct, None) is None:
        accounts[to_acct] = {"id": to_acct, "balance": 0.0}

    accounts[from_acct]['balance'] -= amount
    accounts[to_acct]['balance'] += amount

    update_accounts([from_acct, to_acct, amount])
    # TODO: include originating IP address and authorization signature

    return redirect('/app/', code=302)

@app.route('/api/accounts')
def get_accounts():
    global accounts
    return jsonify(accounts)

# streaming API

@socketio.on('new_client')
def on_join(channel_id):
    global accounts
    socketio.emit('accounts_data', {'accounts': accounts})

if __name__ == '__main__':
    import os
    accounts = json.load(open('data/accounts.json'))
    socketio.run(app, host='0.0.0.0', port=int((os.environ.get("PORT", "9000"))))

