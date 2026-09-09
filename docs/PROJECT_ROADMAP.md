# DPI Trust Framework for Agentic AI

## 1. Project Overview

The DPI Trust Framework for Agentic AI aims to build a trust framework for Agentic AI systems using Digital Public Infrastructure concepts. The framework is intended to help organizations establish trust when autonomous AI agents perform actions and communicate with other agents or services.

The framework addresses the need to establish:

- Who the agent is
- What credentials it possesses
- What authority it has
- What actions it is allowed to perform
- What actions it has performed
- Whether its behaviour can be trusted

## 2. Core Trust Questions

1. Who is this agent?
2. What credentials does it have?
3. What authority has been delegated to it?
4. Is it authenticated?
5. Is it authorized to perform the requested action?
6. What did the agent do?
7. Can the agent's behaviour be trusted?

## 3. Proposed Core Modules

| Module | Responsibility |
| --- | --- |
| Identity & Credentials | Agent registration, DID creation and Verifiable Credentials |
| Delegation & Authority | Managing authority delegated between organizations and agents |
| Authentication & Authorization | Agent authentication and policy-based authorization |
| Audit & Evidence | Recording agent actions and maintaining evidence |
| Trust & Risk Engine | Evaluating behavioural evidence and calculating trust/risk |

## 4. High-Level System Flow

```text
Organization
    ↓
Creates AI Agent
    ↓
Agent receives Decentralized Identity (DID)
    ↓
Agent receives Verifiable Credentials (VC)
    ↓
Authority / Permissions are assigned or delegated
    ↓
Agent communicates with another agent or service
    ↓
Authentication
    ↓
Authorization using policy evaluation
    ↓
Action Allowed or Denied
    ↓
Audit and Evidence Recording
    ↓
Trust and Risk Evaluation
```

## 5. Planned Technology Stack

### Frontend

- React + Vite

### Backend

- Python + FastAPI

### Database

- PostgreSQL

### Infrastructure

- Docker and Docker Compose

### Authorization

- Open Policy Agent (OPA)

### Identity Standards

- W3C Decentralized Identifiers (DID)
- W3C Verifiable Credentials (VC)

### Blockchain / Decentralized Infrastructure

- To be finalized after technical research and feasibility evaluation

The blockchain technology has not yet been finalized. It may be selected based on current ecosystem support and project feasibility.

## 6. Development Phases

### Phase 1 — Project Foundation

Environment setup, repository setup, Docker and infrastructure basics.

### Phase 2 — Agent Registration

Organization and AI agent registration using FastAPI and PostgreSQL.

### Phase 3 — Decentralized Identity

Implementation of DID generation, storage and resolution.

### Phase 4 — Verifiable Credentials

Credential issuance, storage and verification.

### Phase 5 — Delegation and Authority

Implementation of authority delegation between entities and agents.

### Phase 6 — Authentication and Authorization

Authentication flow and OPA-based policy evaluation.

### Phase 7 — Audit and Evidence

Recording agent actions and generating verifiable audit evidence.

### Phase 8 — Trust and Risk Engine

Trust scoring and risk evaluation based on agent behaviour and evidence.

### Phase 9 — Integration

Connect all modules into a complete end-to-end workflow.

### Phase 10 — Dashboard and Demonstration

Develop frontend dashboard and prepare demonstration scenarios.

## 7. Minimum Viable Product (MVP)

The MVP will demonstrate the following end-to-end scenario:

```text
Organization registers in the system
    ↓
Organization creates an AI Agent
    ↓
Agent receives a DID
    ↓
Agent receives a Verifiable Credential
    ↓
Agent is assigned specific permissions
    ↓
Agent sends a request to another agent/service
    ↓
Identity and credentials are verified
    ↓
OPA evaluates authorization policy
    ↓
Request is allowed or denied
    ↓
The event is recorded in the audit system
    ↓
Trust/Risk information is updated
```

## 8. Current Project Status

### Completed

- Development environment setup
- Git installation and configuration
- Docker Desktop installation
- GitHub repository creation
- Local repository setup
- Initial project folder structure
- Initial documentation

### Next Steps

- Learn essential Docker concepts
- Run first Docker container
- Setup PostgreSQL using Docker
- Finalize decentralized identity and blockchain technology selection
- Begin backend implementation
