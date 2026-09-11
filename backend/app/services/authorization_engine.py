from typing import Any, Dict
from app.core.policies import POLICY_CATALOG, PolicyRule
from app.schemas.authorization import AuthorizationDecision

class AuthorizationEngine:
    @classmethod
    def evaluate(cls, input_data: Dict[str, Any]) -> AuthorizationDecision:
        # Validate Input safely without crashing
        try:
            subject = input_data.get("subject", {})
            action = input_data.get("action", {})
            resource = input_data.get("resource", {})
            delegation = input_data.get("delegation", {})
            
            # Extract Identity
            identity_status = subject.get("identity_status")
            
            # Extract Trust
            trust = subject.get("trust", {})
            if "t" not in trust or "u" not in trust or "rr" not in trust:
                return cls._deny("MALFORMED_INPUT", "Missing trust metrics (t, u, rr)")
                
            t = float(trust["t"])
            u = float(trust["u"])
            rr = float(trust["rr"])
            
            # Extract Action & Resource
            action_name = action.get("name")
            resource_type = resource.get("type")
            
            # Extract Delegation
            del_present = bool(delegation.get("is_present", False))
            del_valid = bool(delegation.get("is_valid", False))
            capabilities = delegation.get("capabilities", [])
            
        except (ValueError, TypeError) as e:
            return cls._deny("MALFORMED_INPUT", f"Input data validation failed: {str(e)}")
            
        # Bounds checks
        if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0 and 0.0 <= rr <= 1.0):
            return cls._deny("MALFORMED_INPUT", "Trust values out of bounds [0,1]")

        # Policy Matching (Exact match on resource and action)
        matches = [
            p for p in POLICY_CATALOG 
            if p.resource_type == resource_type and p.action == action_name
        ]
        
        if not matches:
            return cls._deny("NO_MATCHING_POLICY", "No policy matches the requested resource and action")
        
        if len(matches) > 1:
            return cls._deny("AMBIGUOUS_POLICY", "Multiple conflicting policies matched")
            
        rule = matches[0]
        
        # Build evidence
        evidence = {
            "matched_policy": {"resource_type": rule.resource_type, "action": rule.action},
            "required_trust": rule.required_trust,
            "actual_trust": t,
            "maximum_allowed_recent_risk": rule.max_recent_risk,
            "actual_recent_risk": rr,
            "maximum_allowed_uncertainty": rule.max_uncertainty,
            "actual_uncertainty": u,
            "required_capability": rule.required_capability,
            "delegation_validity": del_valid
        }
        
        # Evaluate Precedence
        
        # 1. Identity invalid/revoked
        if identity_status != "active":
            return cls._deny("IDENTITY_INVALID", "Identity is not active", evidence)
            
        # 2. Required delegation missing
        if rule.requires_delegation and not del_present:
            return cls._deny("DELEGATION_INVALID", "Required delegation is missing", evidence)
            
        # 3. Delegation present but invalid
        if rule.requires_delegation and del_present and not del_valid:
            return cls._deny("DELEGATION_INVALID", "Delegation is present but invalid", evidence)
            
        # 4. Required capability missing
        if rule.required_capability and rule.required_capability not in capabilities:
            return cls._deny("CAPABILITY_DENIED", "Required capability missing from delegation", evidence)
            
        # 5. Recent risk exceeds max_recent_risk
        if rr > rule.max_recent_risk:
            return cls._deny("RECENT_RISK_TOO_HIGH", f"Recent risk {rr} exceeds max {rule.max_recent_risk}", evidence)
            
        # 6. Uncertainty exceeds max_uncertainty
        if rule.max_uncertainty is not None and u > rule.max_uncertainty:
            return cls._deny("UNCERTAINTY_TOO_HIGH", f"Uncertainty {u} exceeds max {rule.max_uncertainty}", evidence)
            
        # 7. Trust below required_trust
        if t < rule.required_trust:
            return cls._deny("TRUST_BELOW_THRESHOLD", f"Trust {t} below required {rule.required_trust}", evidence)
            
        # 8. Otherwise -> AUTHORIZED
        return AuthorizationDecision(
            is_allowed=True,
            reason_code="AUTHORIZED",
            explanation="Request authorized according to policy",
            evidence=evidence
        )
        
    @staticmethod
    def _deny(reason_code: str, explanation: str, evidence: Dict[str, Any] = None) -> AuthorizationDecision:
        return AuthorizationDecision(
            is_allowed=False,
            reason_code=reason_code,
            explanation=explanation,
            evidence=evidence or {}
        )
