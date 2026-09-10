import { getContract, parseChaincodeResponse } from "./fabric-client.js";

export class FabricOperationError extends Error {
  constructor(operation, message, options = {}) {
    super(`Fabric operation ${operation} failed: ${message}`, options);
    this.name = "FabricOperationError";
    this.operation = operation;
  }
}

const endorsingOrganizations = ["Org1MSP", "Org2MSP"];

function transactionResult(operation, response, transactionId) {
  return {
    operation,
    result: parseChaincodeResponse(response),
    transactionId,
  };
}

async function evaluate(operation, ...args) {
  try {
    const contract = await getContract();
    const response = await contract.evaluateTransaction(operation, ...args);
    return {
      operation,
      result: parseChaincodeResponse(response),
    };
  } catch (error) {
    throw new FabricOperationError(operation, error.message, { cause: error });
  }
}

async function submit(operation, ...args) {
  try {
    const contract = await getContract();
    const proposal = contract.newProposal(operation, {
      arguments: args,
      endorsingOrganizations,
    });
    const transaction = await proposal.endorse();
    const commit = await transaction.submit();
    const status = await commit.getStatus();
    if (!status.successful) {
      throw new Error(
        `Transaction ${status.transactionId} committed unsuccessfully with status ${status.code}`,
      );
    }
    return transactionResult(
      operation,
      commit.getResult(),
      commit.getTransactionId(),
    );
  } catch (error) {
    throw new FabricOperationError(operation, error.message, { cause: error });
  }
}

export function issueCredential(
  credentialId,
  credentialType,
  issuerDid,
  subjectDid,
  credentialHash,
  issuedAt,
) {
  return submit(
    "IssueCredential",
    credentialId,
    credentialType,
    issuerDid,
    subjectDid,
    credentialHash,
    issuedAt,
  );
}

export function readCredential(credentialId) {
  return evaluate("ReadCredential", credentialId);
}

export function verifyCredential(credentialId, credentialHash) {
  return evaluate("VerifyCredential", credentialId, credentialHash);
}

export function revokeCredential(credentialId, revocationReason, revokedAt) {
  return submit(
    "RevokeCredential",
    credentialId,
    revocationReason,
    revokedAt,
  );
}

export function getCredentialHistory(credentialId) {
  return evaluate("GetCredentialHistory", credentialId);
}

export function issueDelegation(
  delegationId,
  delegatorDid,
  delegateeDid,
  canonicalHash,
  issuedAt,
  expiresAt,
) {
  return submit(
    "IssueDelegation",
    delegationId,
    delegatorDid,
    delegateeDid,
    canonicalHash,
    issuedAt,
    expiresAt,
  );
}

export function readDelegation(delegationId) {
  return evaluate("ReadDelegation", delegationId);
}

export function verifyDelegation(delegationId, canonicalHash) {
  return evaluate("VerifyDelegation", delegationId, canonicalHash);
}

export function revokeDelegation(delegationId, revocationReason, revokedAt) {
  return submit(
    "RevokeDelegation",
    delegationId,
    revocationReason,
    revokedAt,
  );
}

export function getDelegationHistory(delegationId) {
  return evaluate("GetDelegationHistory", delegationId);
}
