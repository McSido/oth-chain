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
Needs:
* peer discovery
* peer management (find/remove disconnected nodes)
* messaging between peers
## [core.py](./core.py)
Start of the blockchain \
Responsible for the setup of the blockchain and networking system

# Information
## Internal communication
Internal communication (between threads) of the blockchain is handled via two Queues \
Communication happens between Blockchain<->Networking
### broadcast_queue
Blockchain -> Networking (-> all nodes)

Message-types
* new_block
* new_transaction

### receive_queue
Networking -> Blockchain 

Message types
* new_block
* new_transaction
* mine