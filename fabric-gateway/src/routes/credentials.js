import { Router } from "express";
import {
  FabricOperationError,
  getCredentialHistory,
  issueCredential,
  readCredential,
  revokeCredential,
  verifyCredential,
} from "../chaincode-operations.js";

const router = Router();

function requireString(value, fieldName) {
  if (typeof value !== "string" || value.trim() === "") {
    const error = new Error(`${fieldName} is required and must be a non-empty string`);
    error.statusCode = 400;
    error.type = "ValidationError";
    throw error;
  }
  return value;
}

function requireBody(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    const error = new Error("Request body must be a JSON object");
    error.statusCode = 400;
    error.type = "ValidationError";
    throw error;
  }
  return body;
}

function successResponse(result, transactionId = null) {
  return {
    success: true,
    result,
    transaction_id: transactionId,
  };
}

function operationResponse(operationResult) {
  return successResponse(
    operationResult.result,
    operationResult.transactionId ?? null,
  );
}

router.post("/issue", async (request, response, next) => {
  try {
    const body = requireBody(request.body);
    const result = await issueCredential(
      requireString(body.credentialId, "credentialId"),
      requireString(body.credentialType, "credentialType"),
      requireString(body.issuerDid, "issuerDid"),
      requireString(body.subjectDid, "subjectDid"),
      requireString(body.credentialHash, "credentialHash"),
      requireString(body.issuedAt, "issuedAt"),
    );
    response.status(201).json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.get("/:credentialId", async (request, response, next) => {
  try {
    const result = await readCredential(
      requireString(request.params.credentialId, "credentialId"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.post("/:credentialId/verify", async (request, response, next) => {
  try {
    const body = requireBody(request.body);
    const result = await verifyCredential(
      requireString(request.params.credentialId, "credentialId"),
      requireString(body.credentialHash, "credentialHash"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.post("/:credentialId/revoke", async (request, response, next) => {
  try {
    const body = requireBody(request.body);
    const result = await revokeCredential(
      requireString(request.params.credentialId, "credentialId"),
      requireString(body.reason, "reason"),
      requireString(body.revokedAt, "revokedAt"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.get("/:credentialId/history", async (request, response, next) => {
  try {
    const result = await getCredentialHistory(
      requireString(request.params.credentialId, "credentialId"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

export { FabricOperationError };
export default router;
