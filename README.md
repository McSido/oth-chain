# Blockchain for the project-study

# Components
## [blockchain.py](./blockchain.py)
Contains an abstract class of a blockchain \
Current implementations:
* [pow_chain.py](./pow_chain.py)\
A Proof-of-Work blockchain that uses sha256 as the hashing-algorithm \
Basic functionality implemented
## [networking.py](./networking-py)
Responsible for all parts of the networking/P2P aspect of the blockchain \
Currently uses UDP packages and is able to receive and send messages\
Needs:
* peer discovery
* peer management (find/remove disconnected nodes)
## [core.py](./core.py)
Start of the blockchain \
Responsible for the setup of the blockchain and networking system

# Instructions
## Setup
1. Clone repo
2. Make copy of repo
3. Change [networking.py](./networking-py) in copy - Line 10: PORT = 6667 
4. Change [networking.py](./networking-py) in copy - Line 63: peer_list.add(('localhost', 6666))
5. Start both [core.py](./core.py) 

## Commands
help: prints commands\
transaction \<from> \<to> \<amount> : Create transaction \
mine: mine a new block \
dump: print blockchain \
exit: exits programm (currently not really working)

# Information
## Internal communication
Internal communication (between threads) of the blockchain is handled via two Queues \
Communication happens between Blockchain<->Networking and CLI<->Blockchain
### broadcast_queue
Blockchain -> Networking (-> all nodes)

Message types
* new_block
* new_transaction

### receive_queue
Networking -> Blockchain
CLI -> Blockchain

Message types
* new_block
* new_transaction
* mine