#!/bin/bash
cd ~/hyperledger/fabric-samples/test-network
./network.sh deployCC -ccn trustledger -ccp ../chaincode/trust-ledger -ccl javascript -ccv 1.3 -ccs 4 -ccep "AND('Org1MSP.peer','Org2MSP.peer')"
