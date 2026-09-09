import dotenv from "dotenv";

dotenv.config();

const requiredVariables = [
  "PORT",
  "FABRIC_CHANNEL_NAME",
  "FABRIC_CHAINCODE_NAME",
  "FABRIC_MSP_ID",
  "FABRIC_PEER_ENDPOINT",
  "FABRIC_USER_CERT_PATH",
  "FABRIC_PRIVATE_KEY_PATH",
  "FABRIC_TLS_CERT_PATH",
  "FABRIC_CONNECTION_PROFILE_PATH",
];

const missingVariables = requiredVariables.filter((name) => {
  const value = process.env[name];
  return typeof value !== "string" || value.trim() === "";
});

if (missingVariables.length > 0) {
  throw new Error(
    `Missing required Fabric Gateway environment variables: ${missingVariables.join(", ")}`,
  );
}

export const config = Object.freeze({
  port: Number.parseInt(process.env.PORT, 10),
  fabricChannelName: process.env.FABRIC_CHANNEL_NAME,
  fabricChaincodeName: process.env.FABRIC_CHAINCODE_NAME,
  fabricMspId: process.env.FABRIC_MSP_ID,
  fabricPeerEndpoint: process.env.FABRIC_PEER_ENDPOINT,
  fabricUserCertPath: process.env.FABRIC_USER_CERT_PATH,
  fabricPrivateKeyPath: process.env.FABRIC_PRIVATE_KEY_PATH,
  fabricTlsCertPath: process.env.FABRIC_TLS_CERT_PATH,
  fabricConnectionProfilePath: process.env.FABRIC_CONNECTION_PROFILE_PATH,
});
