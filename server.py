#!/usr/bin/env python

from flask import Flask, request, render_template, jsonify, redirect, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
import json
import csv

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, async_mode='threading', logger=True)
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

# REST API

def update_accounts(transaction=None):
    global accounts
    socketio.emit('accounts_data', {'accounts': accounts})
    with open('accounts.json', 'w') as jsonfile:
        json.dump(accounts, jsonfile, ensure_ascii=False, sort_keys=True, indent=2)
    if transaction:
        with open('transactions.csv', 'w+') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(transaction)


@app.route('/api/cheque', methods=["POST"])
def send_cheque():
    global accounts
    from_acct = request.form['from_acct']
    to_acct = request.form['to_acct']
    amount = float(request.form['amount'])

    if amount <= 0:
        return "Error: amount was invalid"

    if accounts.get(from_acct, None) is None:
        return "Error: account '{from_acct}' does not exist".format(**locals())

    if accounts[from_acct]['balance'] < amount:
        return "Error: account '{from_acct}' does not have sufficient balance".format(**locals())

    if accounts.get(to_acct, None) is None:
        accounts[to_acct] = {"id": to_acct, "balance": 0.0}

    accounts[from_acct]['balance'] -= amount
    accounts[to_acct]['balance'] += amount

    update_accounts([from_acct, to_acct, amount])

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
    accounts = json.load(open('accounts.json'))
    socketio.run(app, host='0.0.0.0', port='9000')

