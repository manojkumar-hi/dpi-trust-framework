import { Router } from "express";
import {
  FabricOperationError,
  getDelegationHistory,
  issueDelegation,
  readDelegation,
  revokeDelegation,
  verifyDelegation,
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
    const result = await issueDelegation(
      requireString(body.delegationId, "delegationId"),
      requireString(body.delegatorDid, "delegatorDid"),
      requireString(body.delegateeDid, "delegateeDid"),
      requireString(body.canonicalHash, "canonicalHash"),
      requireString(body.issuedAt, "issuedAt"),
      requireString(body.expiresAt, "expiresAt"),
    );
    response.status(201).json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.get("/:delegationId", async (request, response, next) => {
  try {
    const result = await readDelegation(
      requireString(request.params.delegationId, "delegationId"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.post("/:delegationId/verify", async (request, response, next) => {
  try {
    const body = requireBody(request.body);
    const result = await verifyDelegation(
      requireString(request.params.delegationId, "delegationId"),
      requireString(body.canonicalHash, "canonicalHash"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.post("/:delegationId/revoke", async (request, response, next) => {
  try {
    const body = requireBody(request.body);
    const result = await revokeDelegation(
      requireString(request.params.delegationId, "delegationId"),
      requireString(body.reason, "reason"),
      requireString(body.revokedAt, "revokedAt"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

router.get("/:delegationId/history", async (request, response, next) => {
  try {
    const result = await getDelegationHistory(
      requireString(request.params.delegationId, "delegationId"),
    );
    response.json(operationResponse(result));
  } catch (error) {
    next(error);
  }
});

export { FabricOperationError };
export default router;
