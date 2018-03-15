# Blockchain for the project-study

# Components

## [blockchain.py](./blockchain.py)

Contains an abstract class of a blockchain \
Current implementations:

* [pow_chain.py](./pow_chain.py)

A Proof-of-Work blockchain that uses sha256 as the hashing-algorithm \
Basic functionality implemented

## [networking.py](./networking.py)

Responsible for all parts of the networking/P2P aspect of the blockchain \
Uses UDP packages

## [core.py](./core.py)

Start of the blockchain \
Responsible for the setup of the blockchain and networking system \
CLI loop

# Instructions

## Prerequisites

* NaCl (Cryptography)\
 `pip install pynacl`

## Setup

1. Clone repo
2. Make copy of repo
3. Change port in [peers.cfg](./peers.cfg) of the copy
4. Start both [core.py](./core.py) with --port=\<PORT> (Standard port=6666)

## Commands

help: prints commands\
transaction \<to> \<amount> : Create transaction \
mine: mine a new block \
balance [\<name>]: Print balance (name optional) \
dump: print blockchain \
peers: print peers \
key \<filename> : Save current key to \<filename>\
import \<key> \<name> : Imports a public key associated with \<name> from file \<file> to the keystore
deletekey \<name> : Deletes key associated with \<name> from keystore
export \<filename> : Exports one own public key to file \<filename>
save: Save blockchain to bc_file.txt\
exit: exits programm

## Options

```
-p --port=<PORT>   Change port (default is 6666)
-k --key=<PATH>    Load private key from file
-s --store=<PATH>  Sets the name of the keystore file for saving and loading the keystore, defaults to 'keystore'
```

# Information

## Internal communication

Internal communication (between threads) of the blockchain is handled via two Queues \
<img src="./documentation/Blockchain_internal.svg">
Communication happens between Blockchain<->Networking and CLI<->Blockchain

### send_queue

Blockchain -> Networking (-> one/all nodes)

### receive_queue

Networking -> Blockchain \
CLI -> Blockchain

## Networking protocol

Messages are serialized via pythons _pickle_ module \
Messages contain a message-type and message-data