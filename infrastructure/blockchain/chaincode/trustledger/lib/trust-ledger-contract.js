'use strict';

const { Contract } = require('fabric-contract-api');

class TrustLedgerContract extends Contract {

    async CredentialExists(ctx, credentialId) {
        const credentialBytes = await ctx.stub.getState(credentialId);
        return credentialBytes && credentialBytes.length > 0;
    }

    async IssueCredential(
        ctx,
        credentialId,
        credentialType,
        issuerDid,
        subjectDid,
        credentialHash,
        issuedAt
    ) {
        const credentialBytes = await ctx.stub.getState(credentialId);

        if (credentialBytes && credentialBytes.length > 0) {
            const existing = JSON.parse(credentialBytes.toString());
            if (existing.credential_hash === credentialHash) {
                return JSON.stringify(existing);
            }
            throw new Error(`Credential ${credentialId} already exists with a different hash`);
        }

        const credential = {
            credential_id: credentialId,
            credential_type: credentialType,
            issuer_did: issuerDid,
            subject_did: subjectDid,
            credential_hash: credentialHash,
            status: 'active',
            issued_at: issuedAt,
            revoked_at: null,
            revocation_reason: null
        };

        await ctx.stub.putState(
            credentialId,
            Buffer.from(JSON.stringify(credential))
        );

        return JSON.stringify(credential);
    }

    async ReadCredential(ctx, credentialId) {
        const credentialBytes = await ctx.stub.getState(credentialId);

        if (!credentialBytes || credentialBytes.length === 0) {
            throw new Error(`Credential ${credentialId} does not exist`);
        }

        return credentialBytes.toString();
    }

    async VerifyCredential(
        ctx,
        credentialId,
        providedHash
    ) {
        const credentialBytes = await ctx.stub.getState(credentialId);

        if (!credentialBytes || credentialBytes.length === 0) {
            return JSON.stringify({
                valid: false,
                reason: 'Credential does not exist'
            });
        }

        const credential = JSON.parse(credentialBytes.toString());

        if (credential.status !== 'active') {
            return JSON.stringify({
                valid: false,
                reason: `Credential is ${credential.status}`,
                credential_id: credentialId
            });
        }

        if (credential.credential_hash !== providedHash) {
            return JSON.stringify({
                valid: false,
                reason: 'Credential hash mismatch - possible tampering detected',
                credential_id: credentialId
            });
        }

        return JSON.stringify({
            valid: true,
            credential_id: credentialId,
            credential_type: credential.credential_type,
            issuer_did: credential.issuer_did,
            subject_did: credential.subject_did,
            status: credential.status,
            issued_at: credential.issued_at,
            verification_message: 'Credential verified successfully against blockchain ledger'
        });
    }

    async RevokeCredential(
        ctx,
        credentialId,
        revocationReason,
        revokedAt
    ) {
        const credentialBytes = await ctx.stub.getState(credentialId);

        if (!credentialBytes || credentialBytes.length === 0) {
            throw new Error(`Credential ${credentialId} does not exist`);
        }

        const credential = JSON.parse(credentialBytes.toString());

        if (credential.status === 'revoked') {
            if (credential.revocation_reason === revocationReason && credential.revoked_at === revokedAt) {
                return JSON.stringify(credential);
            }
            throw new Error(`Credential ${credentialId} is already revoked with a different reason or timestamp`);
        }

        credential.status = 'revoked';
        credential.revoked_at = revokedAt;
        credential.revocation_reason = revocationReason;

        await ctx.stub.putState(
            credentialId,
            Buffer.from(JSON.stringify(credential))
        );

        return JSON.stringify(credential);
    }

    async GetCredentialHistory(ctx, credentialId) {
        const iterator = await ctx.stub.getHistoryForKey(credentialId);
        const results = [];

        while (true) {
            const result = await iterator.next();

            if (result.value && result.value.value) {
                const value = result.value.value.toString('utf8');

                let record;

                try {
                    record = JSON.parse(value);
                } catch (error) {
                    record = value;
                }

                results.push({
                    tx_id: result.value.txId,
                    timestamp: result.value.timestamp,
                    is_delete: result.value.isDelete,
                    value: record
                });
            }

            if (result.done) {
                await iterator.close();
                break;
            }
        }

        return JSON.stringify(results);
    }
    async DelegationExists(ctx, delegationId) {
        const key = `delegation:${delegationId}`;
        const bytes = await ctx.stub.getState(key);
        return bytes && bytes.length > 0;
    }

    async IssueDelegation(
        ctx,
        delegationId,
        delegatorDid,
        delegateeDid,
        canonicalHash,
        issuedAt,
        expiresAt
    ) {
        const key = `delegation:${delegationId}`;
        const bytes = await ctx.stub.getState(key);

        if (bytes && bytes.length > 0) {
            const existing = JSON.parse(bytes.toString());
            if (existing.canonical_hash === canonicalHash) {
                return JSON.stringify(existing);
            }
            throw new Error(`Delegation ${delegationId} already exists with a different hash`);
        }

        const delegation = {
            delegation_id: delegationId,
            delegator_did: delegatorDid,
            delegatee_did: delegateeDid,
            canonical_hash: canonicalHash,
            status: 'active',
            issued_at: issuedAt,
            expires_at: expiresAt,
            revoked_at: null,
            revocation_reason: null
        };

        await ctx.stub.putState(
            key,
            Buffer.from(JSON.stringify(delegation))
        );

        return JSON.stringify(delegation);
    }

    async ReadDelegation(ctx, delegationId) {
        const key = `delegation:${delegationId}`;
        const bytes = await ctx.stub.getState(key);

        if (!bytes || bytes.length === 0) {
            throw new Error(`Delegation ${delegationId} does not exist`);
        }

        return bytes.toString();
    }

    async VerifyDelegation(
        ctx,
        delegationId,
        providedHash
    ) {
        const key = `delegation:${delegationId}`;
        const bytes = await ctx.stub.getState(key);

        if (!bytes || bytes.length === 0) {
            return JSON.stringify({
                valid: false,
                reason: 'Delegation does not exist'
            });
        }

        const delegation = JSON.parse(bytes.toString());

        if (delegation.status !== 'active') {
            return JSON.stringify({
                valid: false,
                reason: `Delegation is ${delegation.status}`,
                delegation_id: delegationId
            });
        }

        if (delegation.canonical_hash !== providedHash) {
            return JSON.stringify({
                valid: false,
                reason: 'Delegation hash mismatch - possible tampering detected',
                delegation_id: delegationId
            });
        }

        return JSON.stringify({
            valid: true,
            delegation_id: delegationId,
            delegator_did: delegation.delegator_did,
            delegatee_did: delegation.delegatee_did,
            status: delegation.status,
            issued_at: delegation.issued_at,
            expires_at: delegation.expires_at,
            verification_message: 'Delegation verified successfully against blockchain ledger'
        });
    }

    async RevokeDelegation(
        ctx,
        delegationId,
        revocationReason,
        revokedAt
    ) {
        const key = `delegation:${delegationId}`;
        const bytes = await ctx.stub.getState(key);

        if (!bytes || bytes.length === 0) {
            throw new Error(`Delegation ${delegationId} does not exist`);
        }

        const delegation = JSON.parse(bytes.toString());

        if (delegation.status === 'revoked') {
            if (delegation.revocation_reason === revocationReason && delegation.revoked_at === revokedAt) {
                return JSON.stringify(delegation);
            }
            throw new Error(`Delegation ${delegationId} is already revoked with a different reason or timestamp`);
        }

        delegation.status = 'revoked';
        delegation.revoked_at = revokedAt;
        delegation.revocation_reason = revocationReason;

        await ctx.stub.putState(
            key,
            Buffer.from(JSON.stringify(delegation))
        );

        return JSON.stringify(delegation);
    }

    async GetDelegationHistory(ctx, delegationId) {
        const key = `delegation:${delegationId}`;
        const iterator = await ctx.stub.getHistoryForKey(key);
        const results = [];

        while (true) {
            const result = await iterator.next();

            if (result.value && result.value.value) {
                const value = result.value.value.toString('utf8');

                let record;
                try {
                    record = JSON.parse(value);
                } catch (error) {
                    record = value;
                }

                results.push({
                    tx_id: result.value.txId,
                    timestamp: result.value.timestamp,
                    is_delete: result.value.isDelete,
                    value: record
                });
            }

            if (result.done) {
                await iterator.close();
                break;
            }
        }

        return JSON.stringify(results);
    }
}

module.exports = TrustLedgerContract;
