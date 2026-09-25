#!/bin/bash
cd ~/hyperledger/fabric-samples/test-network
export PATH=${PWD}/../bin:$PATH
export FABRIC_CFG_PATH=${PWD}/../config/
source scripts/envVar.sh
setGlobals 1
peer chaincode query -C mychannel -n trustledger -c '{"Args":["DelegationExists","dummy-del"]}'
