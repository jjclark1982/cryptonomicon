# Cryptonomicon

Multi-user simulation of financial accounts and funds transfer

### Installation

Download this project

```shell
    git clone https://github.com/jjclark1982/cryptonomicon.git
    cd cryptonomicon
```

Install pip and download the dependencies for the server (you may want to do this in a virtualenv)

```shell
    pip install -e .
```

Install [Node.js](http://nodejs.org/) and download the dependencies for the client

```shell
    npm install
```

### Usage

Start the server

```shell
    python server.py
```

Connect to [http://localhost:9000/](http://localhost:9000/)

It will display a table of accounts, based on the data in `data/accounts.json`. You can initialize this file with an account that has some money:

```
{
  "0": {
    "id": 0,
    "balance": 1000000.0
  }
}
```

Then go to the [Set Password](http://localhost:9000/app/password.html) link to set the password from this account.

Once it has a password, you can go to the [Make a transaction](http://localhost:9000/app/cheque.html) link to send funds to other accounts. Recipient accounts will be created automatically.
