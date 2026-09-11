import pytest
from app.services.authorization_engine import AuthorizationEngine
from app.core.policies import POLICY_CATALOG, PolicyRule

def build_input(
    resource_type="verifiable_credential",
    action_name="issue",
    identity_status="active",
    t=0.9, u=0.1, rr=0.0,
    del_present=True, del_valid=True,
    capabilities=None
):
    if capabilities is None:
        capabilities = ["credential.issue"]
    return {
        "subject": {
            "identity_status": identity_status,
            "trust": {"t": t, "u": u, "rr": rr}
        },
        "action": {"name": action_name, "risk_level": 0.9},
        "resource": {"type": resource_type},
        "delegation": {
            "is_present": del_present,
            "is_valid": del_valid,
            "capabilities": capabilities
        }
    }

def test_authorized_request():
    inp = build_input()
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is True
    assert dec.reason_code == "AUTHORIZED"

def test_no_matching_policy():
    inp = build_input(resource_type="unknown")
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "NO_MATCHING_POLICY"

def test_invalid_identity():
    inp = build_input(identity_status="revoked")
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "IDENTITY_INVALID"

def test_missing_delegation():
    inp = build_input(del_present=False)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "DELEGATION_INVALID"

def test_invalid_delegation():
    inp = build_input(del_valid=False)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "DELEGATION_INVALID"

def test_missing_capability():
    inp = build_input(capabilities=["dpi.auth.read"])
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "CAPABILITY_DENIED"

def test_excessive_recent_risk():
    inp = build_input(rr=0.95)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "RECENT_RISK_TOO_HIGH"

def test_excessive_uncertainty():
    inp = build_input(u=0.5)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "UNCERTAINTY_TOO_HIGH"

def test_insufficient_trust():
    inp = build_input(t=0.5)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "TRUST_BELOW_THRESHOLD"

def test_exact_threshold_boundary():
    # Requires trust >= 0.8
    inp = build_input(t=0.8)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is True

def test_malformed_input():
    dec = AuthorizationEngine.evaluate({})
    assert dec.is_allowed is False
    assert dec.reason_code == "MALFORMED_INPUT"

    # Out of bounds trust
    inp = build_input(t=1.5)
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "MALFORMED_INPUT"

def test_conflicting_policy(monkeypatch):
    # Temporarily add conflicting policy
    rule_copy = PolicyRule(
        resource_type="system_status", action="read", action_risk=0.1,
        required_trust=0.0, max_recent_risk=0.9, max_uncertainty=1.0,
        required_capability=None, requires_delegation=False
    )
    monkeypatch.setattr('app.services.authorization_engine.POLICY_CATALOG', POLICY_CATALOG + [rule_copy])
    inp = build_input(resource_type="system_status", action_name="read")
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "AMBIGUOUS_POLICY"

def test_deterministic_repeated_evaluation():
    inp = build_input()
    dec1 = AuthorizationEngine.evaluate(inp)
    dec2 = AuthorizationEngine.evaluate(inp)
    assert dec1.model_dump() == dec2.model_dump()

def test_action_risk_does_not_change_required_trust():
    # Send very low action risk. 
    # Engine must still evaluate against the policy's required_trust (0.8)
    inp = build_input()
    inp["action"]["risk_level"] = 0.01
    inp["subject"]["trust"]["t"] = 0.5  # Below required 0.8
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "TRUST_BELOW_THRESHOLD"

def test_hard_boundaries_take_precedence_over_trust():
    # Valid trust, but missing capability
    inp = build_input(t=1.0, rr=0.0, u=0.0, capabilities=["unknown"])
    dec = AuthorizationEngine.evaluate(inp)
    assert dec.is_allowed is False
    assert dec.reason_code == "CAPABILITY_DENIED"

def test_evidence_structure():
    inp = build_input()
    dec = AuthorizationEngine.evaluate(inp)
    assert "matched_policy" in dec.evidence
    assert "actual_trust" in dec.evidence
    assert "actual_recent_risk" in dec.evidence
