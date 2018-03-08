# Blockchain for the project-study

# Components
## [blockchain.py](./blockchain.py)
Contains an abstract class of a blockchain \
Current implementations:
* [pow_chain.py](./pow_chain.py)\
A Proof-of-Work blockchain that uses sha256 as the hashing-algorithm \
Basic functionality implemented
## [networking.py](./networking.py)
Responsible for all parts of the networking/P2P aspect of the blockchain \
Uses UDP packages\
## [core.py](./core.py)
Start of the blockchain \
Responsible for the setup of the blockchain and networking system \
CLI loop

# Instructions
## Setup
1. Clone repo
2. Make copy of repo
3. Change port in [peers.cfg](./peers.cfg) of the copy
5. Start both [core.py](./core.py) with --port=\<PORT> (Standard port=6666)

## Commands
help: prints commands\
transaction \<from> \<to> \<amount> : Create transaction \
mine: mine a new block \
dump: print blockchain \
peers: print peers \
key \<filename> : Save current key to \<filename>\
save: Save blockchain to bc_file.txt\
exit: exits programm

## Options
```
-p --port=<PORT>   Change port (default is 6666)
-k --key=<PATH>    Load private key from file
```
# Information
## Internal communication
Internal communication (between threads) of the blockchain is handled via two Queues \
Communication happens between Blockchain<->Networking and CLI<->Blockchain
### send_queue
Blockchain -> Networking (-> one/all nodes)

### receive_queue
Networking -> Blockchain \
CLI -> Blockchain

## Networking protocol
Messages are serialized via pythons _pickle_ module \
Messages contain a message-type and message-data