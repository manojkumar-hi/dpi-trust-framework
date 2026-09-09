import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createPrivateKey } from "node:crypto";
import * as grpc from "@grpc/grpc-js";
import { connect, signers } from "@hyperledger/fabric-gateway";
import { config } from "./config.js";

let gateway;
let grpcClient;
let contract;
let connectionPromise;

function readFabricFile(path, description) {
  try {
    return readFileSync(path);
  } catch (error) {
    throw new Error(
      `Unable to read ${description} at ${path}: ${error.message}`,
      { cause: error },
    );
  }
}

export function parseChaincodeResponse(response) {
  const text = Buffer.from(response).toString("utf8");
  if (text.length === 0) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function createFabricConnection() {
  const certificate = readFabricFile(
    config.fabricUserCertPath,
    "Fabric user certificate",
  );
  const privateKey = readFabricFile(
    config.fabricPrivateKeyPath,
    "Fabric private key",
  );
  const tlsCertificate = readFabricFile(
    config.fabricTlsCertPath,
    "Fabric peer TLS certificate",
  );

  const client = new grpc.Client(
    config.fabricPeerEndpoint,
    grpc.credentials.createSsl(tlsCertificate),
  );
  const fabricIdentity = {
    mspId: config.fabricMspId,
    credentials: certificate,
  };
  const signer = signers.newPrivateKeySigner(
    createPrivateKey({ key: privateKey, format: "pem" }),
  );

  try {
    const fabricGateway = connect({
      client,
      identity: fabricIdentity,
      signer,
    });
    const network = fabricGateway.getNetwork(config.fabricChannelName);
    const fabricContract = network.getContract(config.fabricChaincodeName);

    grpcClient = client;
    gateway = fabricGateway;
    contract = fabricContract;
    return fabricContract;
  } catch (error) {
    client.close();
    throw new Error(`Unable to connect to Fabric Gateway: ${error.message}`, {
      cause: error,
    });
  }
}

export async function connectToFabric() {
  if (contract) {
    return contract;
  }

  if (!connectionPromise) {
    connectionPromise = createFabricConnection().catch((error) => {
      connectionPromise = undefined;
      throw error;
    });
  }

  return connectionPromise;
}

export async function getContract() {
  return connectToFabric();
}

export function closeFabricConnection() {
  if (gateway) {
    gateway.close();
  }
  if (grpcClient) {
    grpcClient.close();
  }

  gateway = undefined;
  grpcClient = undefined;
  contract = undefined;
  connectionPromise = undefined;
}

export async function testReadCredential(credentialId = "CRED001") {
  const fabricContract = await getContract();
  const response = await fabricContract.evaluateTransaction(
    "ReadCredential",
    credentialId,
  );
  return parseChaincodeResponse(response);
}

const isMainModule = process.argv[1]
  ? fileURLToPath(import.meta.url) === process.argv[1]
  : false;

if (isMainModule) {
  try {
    await testReadCredential();
    console.log("ReadCredential(CRED001): SUCCESS");
  } catch (error) {
    console.error(`ReadCredential(CRED001): FAILED - ${error.message}`);
    process.exitCode = 1;
  } finally {
    closeFabricConnection();
  }
}
