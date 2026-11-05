import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import { agentsApi } from '../api/agents';
import { credentialsApi } from '../api/credentials';
import { delegationsApi } from '../api/delegations';
import { trustApi } from '../api/trust';
import { useAuth } from '../context/AuthContext';
import {
  createAgentPresentation,
  createAgentWallet,
  createIdempotencyKey,
  getStoredAgentWallet,
} from '../api/agentWallet';

const sampleEmployeeId = 'EMP-1001';
const sampleLeaveRequestId = 'LR-2026-001';

const intentPatterns = [
  {
    capability: 'hr.plan_training_program',
    test: /\b(plan|prepare|design|create)\b.*\b(training|workforce development)\b|\b(training|workforce development)\b.*\b(plan|program)\b/i,
  },
  {
    capability: 'hr.submit_leave_request',
    test: /\b(apply|submit|request|book)\b.*\b(leave|time off|vacation)\b|\b(leave|time off|vacation)\b.*\b(apply|submit|request|book)\b/i,
  },
  {
    capability: 'hr.calculate_leave_balance',
    test: /\b(balance|remaining|left|calculate)\b.*\b(leave|vacation|days off)\b|\b(leave|vacation)\b.*\b(balance|remaining|left)\b/i,
  },
  { capability: 'hr.view_holiday_calendar', test: /\b(holiday|holidays|calendar|days off)\b/i },
  { capability: 'hr.check_leave_status', test: /\b(status|progress|approved|pending)\b.*\b(leave|request)\b|\b(leave|request)\b.*\b(status|progress)\b/i },
  { capability: 'hr.view_employee_profile', test: /\b(profile|details|information)\b.*\b(employee|staff|person)\b|\b(employee|staff)\b.*\b(profile|details|information)\b/i },
  { capability: 'hr.read_policies', test: /\b(policy|policies|handbook|rules)\b/i },
];

const identifyCapability = (prompt) => intentPatterns.find((item) => item.test.test(prompt))?.capability;

const identifyTemplateCapability = (prompt, tools = []) => {
  const normalizedPrompt = prompt.toLowerCase().replaceAll('_', ' ');
  return tools.find((tool) => {
    const toolName = tool.name.toLowerCase().replaceAll('_', ' ');
    const capabilityCode = tool.capability_code.toLowerCase();
    return normalizedPrompt.includes(toolName) || normalizedPrompt.includes(capabilityCode);
  })?.capability_code;
};

const conversationalResponse = (prompt, template, isHrTemplate) => {
  const normalizedPrompt = prompt.trim().toLowerCase();
  const agentName = template?.display_name || (isHrTemplate ? 'HR Agent' : 'this agent');
  const availableActions = (template?.tools || [])
    .map((tool) => tool.name.replaceAll('_', ' '))
    .join(', ');

  if (/^(hi|hello|hey|good morning|good afternoon|good evening)\b[!. ,]*$/i.test(normalizedPrompt)) {
    return `Hello! I’m the ${agentName}. I can help with ${availableActions || 'my registered actions'}.`;
  }
  if (/^(thanks|thank you|thx)\b[!. ,]*$/i.test(normalizedPrompt)) {
    return `You’re welcome. I’m here for ${availableActions || 'my registered actions'}.`;
  }
  if (/^(help|what can you do|what do you do|capabilities)\b[?.! ]*$/i.test(normalizedPrompt)) {
    return `I can help with: ${availableActions || 'no actions are currently registered'}.`;
  }
  return null;
};

const resolveAction = (capability, prompt) => {
  const employeeId = prompt.match(/\bEMP-[A-Z0-9-]+\b/i)?.[0] || sampleEmployeeId;
  const requestId = prompt.match(/\bLR-[A-Z0-9-]+\b/i)?.[0] || sampleLeaveRequestId;
  const year = Number(prompt.match(/\b20\d{2}\b/)?.[0] || new Date().getFullYear());
  const dates = prompt.match(/\b20\d{2}-\d{2}-\d{2}\b/g) || [];
  const department = prompt.match(/\bfor\s+(?:the\s+)?([a-z][a-z -]{2,60}?)(?:\s+team|\s+department)\b/i)?.[1]?.trim() || 'Customer Support';
  const trainingTopic = prompt.match(/\b(?:on|about|covering)\s+(.+?)(?:\s+for\b|\s*$)/i)?.[1]?.trim() || 'Service quality and compliance';

  switch (capability) {
    case 'hr.plan_training_program':
      return { payload: { department, training_topic: trainingTopic } };
    case 'hr.read_policies':
      return { payload: {} };
    case 'hr.calculate_leave_balance':
    case 'hr.view_employee_profile':
      return { payload: { employee_id: employeeId } };
    case 'hr.view_holiday_calendar':
      return { payload: { year } };
    case 'hr.check_leave_status':
      return { payload: { request_id: requestId } };
    case 'hr.submit_leave_request': {
      const reason = prompt.match(/\b(?:because|reason(?:\s+is)?)\b\s*[:,-]?\s*(.+)$/i)?.[1]?.trim();
      if (dates.length < 2 || !reason) {
        return {
          clarification: 'To submit a sample leave request, include a start date, end date, and reason. Example: “Request leave for EMP-1001 from 2026-11-12 to 2026-11-13 because of a family event.”',
        };
      }
      return { payload: { employee_id: employeeId, start_date: dates[0], end_date: dates[1], reason } };
    }
    default:
      return { clarification: 'I could not match that request to one of this template’s HR actions. Try asking about policies, leave balance, holidays, leave request status, submitting leave, or an employee profile.' };
  }
};

const resolveTemplateAction = (capability, prompt) => {
  switch (capability) {
    case 'finance.read_budget':
      return { payload: { cost_center: prompt.match(/\bCC-\d+\b/i)?.[0] || 'CC-100' } };
    case 'finance.review_invoice':
      return { payload: { invoice_id: prompt.match(/\bINV-[A-Z0-9-]+\b/i)?.[0] || 'INV-2026-001' } };
    case 'finance.prepare_payment': {
      const amount = prompt.match(/(?:amount|pay)\s*(?:of|:)?\s*\$?([0-9]+(?:\.[0-9]{1,2})?)/i)?.[1] || '1250.00';
      return {
        payload: {
          invoice_id: prompt.match(/\bINV-[A-Z0-9-]+\b/i)?.[0] || 'INV-2026-001',
          amount,
          currency: prompt.match(/\b(USD|EUR|GBP|INR)\b/i)?.[1]?.toUpperCase() || 'USD',
        },
      };
    }
    default:
      return { payload: {} };
  }
};

const detailMessage = (error) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.explanation) return `${detail.reason || 'Request denied'}: ${detail.explanation}`;
  if (detail?.error) return `${detail.error}${detail.reason ? ` (${detail.reason})` : ''}${detail.explanation ? `: ${detail.explanation}` : ''}`;
  return error?.message || 'The action could not be completed.';
};

const resultText = (responseResult) => {
  let result = responseResult;
  while (result && typeof result === 'object' && Object.hasOwn(result, 'result')) {
    result = result.result;
  }

  if (typeof result === 'string') {
    const trimmed = result.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try { result = JSON.parse(trimmed); } catch { return result; }
    } else {
      return result || 'The action completed.';
    }
  }
  if (!result || typeof result !== 'object') return String(result ?? 'The action completed.');
  if (result.error) return result.error;

  const isSample = result.prototype === true;
  const sampleNote = isSample ? '\n\nThis response uses demonstration data.' : '';
  const formatRecord = (record) => Object.entries(record)
    .map(([key, value]) => `• ${key.replaceAll('_', ' ')}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join('\n');

  if (result.budget) {
    return `Budget summary:\n${formatRecord(result.budget)}${sampleNote}`;
  }
  if (result.invoice) {
    return `Invoice review:\n${formatRecord(result.invoice)}\nReview: ${formatRecord(result.review || {})}${sampleNote}`;
  }
  if (result.payment) {
    return `Payment preparation:\n${formatRecord(result.payment)}${result.notice ? `\n\n${result.notice}` : ''}${sampleNote}`;
  }
  if (result.training_plan) {
    return `Workforce training plan for ${result.department || 'the selected department'}:\n• Topic: ${result.training_topic}\n• Budget: ${result.budget_summary?.remaining || 'unknown'} ${result.budget_summary?.currency || ''} remaining (${result.budget_summary?.cost_center || 'budget'})\n• Audience: ${result.training_plan.audience}\n• Modules: ${result.training_plan.modules.join('; ')}\n• Delivery: ${result.training_plan.delivery}\n\n${result.notice || ''}`;
  }
  if (Array.isArray(result.policies)) {
    const policies = result.policies.map((policy) => `• ${policy.title}: ${policy.summary}`).join('\n');
    return `Here are the HR policies:\n${policies}${sampleNote}`;
  }
  if (result.profile) {
    const fields = Object.entries(result.profile)
      .map(([key, value]) => `• ${key.replaceAll('_', ' ')}: ${String(value)}`).join('\n');
    return `Employee profile:\n${fields}${sampleNote}`;
  }
  if (Array.isArray(result.holidays)) {
    const holidays = result.holidays.map((holiday) => `• ${holiday.date}: ${holiday.name}`).join('\n');
    return `Holiday calendar for ${result.year ?? 'the selected year'}:\n${holidays}${sampleNote}`;
  }
  if ('annual_days_remaining' in result || 'sick_days_remaining' in result) {
    const balance = [
      `Leave balance for ${result.employee_id || 'the employee'}:`,
      result.annual_days_remaining != null && `• Annual leave remaining: ${result.annual_days_remaining} days`,
      result.sick_days_remaining != null && `• Sick leave remaining: ${result.sick_days_remaining} days`,
    ].filter(Boolean).join('\n');
    return `${balance}${sampleNote}`;
  }

  const hiddenFields = new Set(['prototype', 'source', 'notice']);
  const details = Object.entries(result)
    .filter(([key]) => !hiddenFields.has(key))
    .map(([key, value]) => `• ${key.replaceAll('_', ' ')}: ${Array.isArray(value) ? value.join(', ') : typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join('\n');
  const notice = result.notice ? `\n\n${result.notice}` : '';
  return `${details || 'The action completed.'}${notice}${sampleNote}`;
};

export const AgentInteractionModal = ({ agent, onClose }) => {
  const { orgId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [setupState, setSetupState] = useState('idle');
  const [runBusy, setRunBusy] = useState(false);
  const [error, setError] = useState('');
  const [identity, setIdentity] = useState(null);
  const [template, setTemplate] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [wallet, setWallet] = useState(null);
  const [credential, setCredential] = useState(null);
  const [delegations, setDelegations] = useState([]);
  const [loadedAt, setLoadedAt] = useState(0);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [organizationAgents, setOrganizationAgents] = useState([]);
  const [targetAgentId, setTargetAgentId] = useState(agent.id);
  const [trustData, setTrustData] = useState(null);
  const [trustLoading, setTrustLoading] = useState(false);
  const [trustError, setTrustError] = useState('');
  const setupAttempted = useRef(false);
  const chatEnd = useRef(null);
  const isHrTemplate = agent.template_id === 'hr_agent';
  const targetAgent = useMemo(
    () => organizationAgents.find((item) => item.id === targetAgentId) || agent,
    [agent, organizationAgents, targetAgentId]
  );
  const targetTemplate = useMemo(
    () => templates.find((item) => item.template_id === targetAgent.template_id && item.template_version === targetAgent.template_version) || template,
    [targetAgent, template, templates]
  );
  const targetIsHrTemplate = targetAgent.template_id === 'hr_agent';

  const evaluateTrust = async () => {
    setTrustLoading(true);
    setTrustError('');
    try {
      setTrustData(await trustApi.getTrustScore(targetAgent.id));
    } catch (trustRequestError) {
      setTrustError(detailMessage(trustRequestError));
    } finally {
      setTrustLoading(false);
    }
  };

  const load = useCallback(async () => {
    try {
      const [availableTemplates, agentIdentity, credentials, orgDelegations, localWallet, orgAgents] = await Promise.all([
        agentsApi.getTemplates(),
        agentsApi.getAgentIdentity(agent.id),
        credentialsApi.getCredentials({ subject_agent_id: agent.id }),
        delegationsApi.getDelegations(),
        getStoredAgentWallet(agent.id),
        agentsApi.getAgents(orgId),
      ]);
      setIdentity(agentIdentity);
      setTemplates(availableTemplates);
      setTemplate(availableTemplates.find((item) => item.template_id === agent.template_id && item.template_version === agent.template_version) || null);
      setOrganizationAgents(orgAgents);
      setTargetAgentId(agent.id);
      setWallet(localWallet || null);
      const activeCredential = credentials.find((item) => item.status === 'active' && item.vc_jwt) || null;
      setCredential(activeCredential);
      if (localWallet?.privateKey && activeCredential && agentIdentity.public_key === localWallet.publicKeyB64) setSetupState('ready');
      setDelegations(orgDelegations.filter((item) => item.delegator_organization_id === orgId));
      setLoadedAt(Date.now());
    } catch (loadError) {
      setError(detailMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [agent, orgId]);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => { if (!cancelled) load(); });
    return () => { cancelled = true; };
  }, [load]);

  const targetDelegations = useMemo(() => delegations.filter((item) => item.status === 'active'
      && item.delegatee_agent_id === targetAgent.id
      && new Date(item.starts_at).getTime() <= loadedAt
      && new Date(item.expires_at).getTime() > loadedAt), [delegations, loadedAt, targetAgent.id]);

  const delegatedCodes = useMemo(() => new Set(targetDelegations.flatMap((delegation) => (delegation.capabilities || [])
    .filter((capability) => capability.scope?.permission !== 'DENIED')
    .map((capability) => capability.capability_code))), [targetDelegations]);

  const setupWallet = useCallback(async () => {
    setSetupState('busy');
    setError('');
    try {
      let localWallet = await getStoredAgentWallet(agent.id);
      if (!localWallet?.privateKey || !localWallet?.publicKeyB64) localWallet = await createAgentWallet(agent.id);
      const currentIdentity = identity || await agentsApi.getAgentIdentity(agent.id);
      const activeIdentity = currentIdentity.public_key === localWallet.publicKeyB64
        ? currentIdentity
        : await agentsApi.rekeyIdentity(agent.id, localWallet.publicKeyB64);
      setIdentity(activeIdentity);
      setWallet(localWallet);

      let currentCredential = credential;
      if (!currentCredential?.vc_jwt) {
        currentCredential = await credentialsApi.issueCredential({
          issuer_organization_id: orgId,
          subject_agent_id: agent.id,
          credential_type: 'AgentInteractionCredential',
          credential_data: {
            agentId: agent.id,
            templateId: agent.template_id,
            templateVersion: agent.template_version,
            purpose: 'Agent interaction',
          },
          expires_at: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
        });
      }
      setCredential(currentCredential);
      setSetupState('ready');
    } catch (setupError) {
      setSetupState('error');
      setError(`Secure setup could not finish: ${detailMessage(setupError)}`);
    }
  }, [agent, credential, identity, orgId]);

  useEffect(() => {
    if (!loading && identity && (!wallet?.privateKey || !credential?.vc_jwt || identity.public_key !== wallet.publicKeyB64) && !setupAttempted.current) {
      setupAttempted.current = true;
      setupWallet();
    }
  }, [credential, identity, loading, setupWallet, wallet]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages, runBusy]);

  const runPrompt = async (event) => {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt || runBusy) return;
    setMessage('');
    setError('');
    setMessages((current) => [...current, { role: 'user', text: prompt }]);

    const localResponse = conversationalResponse(prompt, targetTemplate, targetIsHrTemplate);
    if (localResponse) {
      setMessages((current) => [...current, { role: 'assistant', text: localResponse }]);
      return;
    }

    const capability = targetIsHrTemplate
      ? identifyCapability(prompt)
      : identifyTemplateCapability(prompt, targetTemplate?.tools);
    if (!capability || !targetTemplate?.tools.some((tool) => tool.capability_code === capability)) {
      const availableActions = (targetTemplate?.tools || []).map((tool) => tool.name.replaceAll('_', ' ')).join(', ');
      setMessages((current) => [...current, {
        role: 'assistant',
        text: `I’m the ${targetTemplate?.display_name || 'selected agent'}, so I can’t answer that question. I can help with: ${availableActions || 'no registered actions'}.`,
      }]);
      return;
    }

    const action = targetIsHrTemplate ? resolveAction(capability, prompt) : resolveTemplateAction(capability, prompt);
    if (action.clarification) {
      setMessages((current) => [...current, { role: 'assistant', text: action.clarification }]);
      return;
    }
    if (!wallet?.privateKey || !identity?.did || !credential?.vc_jwt) {
      setError('Secure setup is still running. Please wait, or retry setup if an error is shown.');
      return;
    }

    setRunBusy(true);
    setMessages((current) => [...current, {
      role: 'assistant',
      text: targetAgent.id === agent.id ? `I’ll check “${capability}” through the Gateway.` : `I’ll ask ${targetAgent.name} to handle “${capability}” through the Gateway.`,
      capability,
      pending: true,
    }]);
    try {
      const actionDelegation = targetDelegations.find((delegation) => (delegation.capabilities || [])
        .some((delegatedCapability) => delegatedCapability.capability_code === capability
          && delegatedCapability.scope?.permission !== 'DENIED'));
      if (actionDelegation) {
        const verified = await delegationsApi.verifyDelegation(actionDelegation.id);
        if (!verified.valid) throw new Error(`Delegation verification failed: ${verified.verification_message}`);
      }
      const challengeResponse = await apiClient.post('/auth/challenges');
      const challenge = challengeResponse.data;
      const didDocument = await agentsApi.getAgentDidDocument(identity.did);
      const targetIdentity = targetAgent.id === agent.id
        ? identity
        : await agentsApi.getAgentIdentity(targetAgent.id);
      const keyId = didDocument.authentication?.[0];
      if (!keyId) throw new Error('No active signing key is published for this agent. Retry secure setup.');
      const vpJwt = await createAgentPresentation({
        privateKey: wallet.privateKey,
        did: identity.did,
        keyId,
        nonce: challenge.nonce,
        audience: challenge.audience,
        credential: credential.vc_jwt,
      });
      const response = await agentsApi.invokeGateway({
        challenge_id: challenge.challenge_id,
        source_agent_did: identity.did,
        target_agent_did: targetIdentity.did,
        action_type: capability,
        resource_id: `local-prototype:${targetAgent.id}`,
        payload: action.payload,
        delegation_id: actionDelegation?.id || null,
        timestamp: new Date().toISOString(),
        authentication_proof: { type: 'VerifiablePresentation', vp_jwt: vpJwt },
      }, createIdempotencyKey());
      setMessages((current) => [
        ...current.slice(0, -1),
        { role: 'assistant', capability, text: resultText(response.result), status: response.status, executionId: response.execution_id },
      ]);
    } catch (runError) {
      const denial = runError.response?.status === 403;
      setMessages((current) => [
        ...current.slice(0, -1),
        { role: 'assistant', capability, text: denial ? `The Gateway denied this action. ${detailMessage(runError)}` : detailMessage(runError), status: denial ? 'DENIED' : 'FAILED' },
      ]);
    } finally {
      setRunBusy(false);
    }
  };

  if (!agent) return null;

  return (
    <div className="agent-chat-backdrop" role="dialog" aria-modal="true" aria-labelledby="agent-chat-title">
      <section className="agent-chat-window" aria-label="Agent chat">
        <header className="agent-chat-header">
          <div>
            <h2 id="agent-chat-title">Try {agent.name}</h2>
            <p>{template?.display_name || agent.template_id} · {agent.template_version || 'version not set'}</p>
          </div>
          <button className="agent-chat-close" type="button" onClick={onClose} aria-label="Close chat">×</button>
        </header>

        <div className="agent-chat-notice">
            Demonstration data: this agent is not connected to an enterprise system.
        </div>
        {error && <div className="agent-chat-error" role="alert">{error}</div>}

        <main className="agent-chat-content">
          <section className="agent-chat-conversation" aria-label="Conversation">
            {loading ? <div className="agent-chat-empty">Loading agent access…</div> : (
              <>
                <div className="agent-chat-messages" aria-live="polite">
                  {!messages.length && <div className="agent-chat-empty">
                    <strong>Ask the agent for help.</strong>
                    <span>{targetIsHrTemplate ? 'For example: “How much annual leave does EMP-1001 have left?”' : `Try: “${targetTemplate?.tools?.[0]?.name?.replaceAll('_', ' ') || 'use an available capability'}”`}</span>
                  </div>}
                  {messages.map((entry, index) => (
                    <article className={`agent-chat-message ${entry.role === 'user' ? 'from-user' : 'from-agent'}`} key={`${index}-${entry.role}`}>
                      <div className="agent-chat-speaker">{entry.role === 'user' ? 'You' : targetAgent.name}</div>
                      <p>{entry.text}</p>
                      {entry.pending && <span className="agent-chat-status">Checking with Gateway…</span>}
                      {entry.status && <span className={`agent-chat-status ${entry.status === 'SUCCESS' ? 'is-success' : entry.status === 'DENIED' ? 'is-denied' : ''}`}>{entry.status}{entry.executionId ? ` · ${entry.executionId}` : ''}</span>}
                    </article>
                  ))}
                  <div ref={chatEnd} />
                </div>

                {setupState === 'busy' && <div className="agent-chat-setup"><span className="spinner-border spinner-border-sm" /> Preparing secure agent access…</div>}
                {setupState === 'error' && <div className="agent-chat-setup">
                  <span>Secure setup needs another try before the agent can act.</span>
                  <button className="btn btn-outline-primary btn-sm" type="button" onClick={setupWallet}>Retry setup</button>
                </div>}
                <form className="agent-chat-composer" onSubmit={runPrompt}>
                  <textarea
                    aria-label="Message the agent"
                    placeholder="Message the agent… (Enter to send, Shift+Enter for a new line)"
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                    disabled={loading || setupState === 'busy' || runBusy}
                    rows="2"
                  />
                  <button className="btn btn-primary" type="submit" disabled={loading || setupState === 'busy' || runBusy || !message.trim()}>
                    {runBusy ? 'Working…' : 'Send'}
                  </button>
                </form>
              </>
            )}
          </section>
          <aside className="agent-chat-security-sidebar" aria-label="Security context">
            <section className="agent-chat-trust" aria-label="Trust evaluation">
              <div className="agent-chat-security-heading">
                <div>
                  <h3>Trust Evaluation</h3>
                  <p>Signals for {targetAgent.name}.</p>
                </div>
                <button className="btn btn-sm btn-outline-primary" type="button" onClick={evaluateTrust} disabled={trustLoading}>
                  {trustLoading ? 'Evaluating…' : 'Evaluate Trust'}
                </button>
              </div>
              {trustError && <div className="agent-chat-error" role="alert">{trustError}</div>}
              {trustData && <div className="agent-chat-trust-metrics">
                <strong>Trust<br /><span>{((trustData.trust ?? 0) * 100).toFixed(1)}%</span></strong>
                <span>Uncertainty<br /><b>{((trustData.uncertainty ?? 0) * 100).toFixed(1)}%</b></span>
                <span>Risk<br /><b>{((trustData.recent_risk ?? 0) * 100).toFixed(1)}%</b></span>
              </div>}
            </section>
            <div className="agent-chat-target-picker">
              <label htmlFor="agent-chat-target">Request execution from</label>
              <select id="agent-chat-target" value={targetAgent.id} onChange={(event) => { setTargetAgentId(event.target.value); setTrustData(null); }} disabled={runBusy || loading}>
                {(organizationAgents.length ? organizationAgents : [agent]).map((candidate) => (
                  <option value={candidate.id} key={candidate.id}>{candidate.name}</option>
                ))}
              </select>
              <p>Signed by {agent.name}. The selected agent verifies the request before acting.</p>
            </div>
            <section className="agent-chat-capabilities" aria-label="Agent capabilities">
              <h3>{targetAgent.name} capabilities</h3>
              {(targetTemplate?.tools || []).map((tool) => {
                const allowed = delegatedCodes.has(tool.capability_code);
                return <div className="agent-chat-capability" key={tool.capability_code}>
                  <span>{tool.name.replaceAll('_', ' ')}</span>
                  <span className={`agent-chat-badge ${allowed ? 'is-allowed' : 'is-denied'}`}>{allowed ? 'Allowed' : 'Not delegated'}</span>
                </div>;
              })}
            </section>
          </aside>
        </main>

        <footer className="agent-chat-footer">
          <span>{setupState === 'ready' ? 'Secure access is ready in this browser.' : 'Secure setup runs automatically when this window opens.'}</span>
          <div className="agent-chat-footer-actions">
            <Link className="agent-chat-audit-link" to="/audit">View Audit Trail</Link>
            <button className="btn btn-light border" type="button" onClick={onClose}>Close</button>
          </div>
        </footer>
      </section>
    </div>
  );
};
