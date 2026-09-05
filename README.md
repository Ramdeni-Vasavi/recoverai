# RecoverAI

## AI-Assisted Revenue Recovery for Failed Payments

RecoverAI is an AI/ML-assisted revenue recovery prototype designed to help businesses make safer and more intelligent decisions for failed payments.

Instead of applying the same recovery strategy to every failed payment, RecoverAI evaluates payment signals, estimates recovery probability, selects a suitable recovery action, optimizes the recovery strategy, applies safety guardrails, and executes the approved action in a controlled simulation environment.

The system is designed around the following recovery pipeline:

**Failed Payment → ML Prediction → Recovery Decision → Optimization → Guardrails → Execution → Dashboard & Audit**

---

## Problem

Failed payments can directly contribute to revenue leakage for businesses.

A simple "retry everything" approach can result in:

- Unnecessary retry attempts
- Poor customer experience
- Inefficient recovery strategies
- Repeated attempts on unsuitable payments
- Increased operational overhead

RecoverAI addresses this problem by introducing prediction, decisioning, optimization, and safety controls into the payment recovery workflow.

---

## Solution

RecoverAI provides an end-to-end recovery decision pipeline for failed payments.

### 1. Payment Ingestion

Payment information can enter the system through:

- Backend payment APIs
- Razorpay webhook events

The Razorpay webhook integration validates the webhook signature before processing supported payment events.

Currently supported webhook events include:

- `payment.failed`
- `payment.captured`

Razorpay integration is implemented as a secure integration boundary. The current prototype does not make outbound Razorpay API calls for real payment retries.

---

### 2. ML-Based Recovery Prediction

RecoverAI uses a machine-learning model to estimate the probability that a failed payment can be recovered.

The current prototype uses:

- Logistic Regression
- Feature-based prediction
- Runtime model training
- Versioned model identification

The current training data is intentionally synthetic/demo data and is **not production Razorpay customer data**.

Therefore, the prototype does not claim production-level model accuracy or performance.

The prediction output is used by the recovery decision layer.

---

### 3. Recovery Decision Engine

The recovery decision layer converts the predicted recovery probability and payment state into a controlled recovery action.

Supported recovery actions are:

- `retry_payment`
- `create_payment_link`
- `send_reminder`
- `stop_recovery`

The current policy applies probability thresholds, retry limits, and payment failure conditions.

The prototype's automated policy primarily selects:

- Retry payment for sufficiently high recovery probability
- Payment link for medium recovery probability
- Stop recovery when recovery is unlikely or the failure condition is non-retryable

The `send_reminder` action is supported by the recovery action model, while the current decision policy does not automatically select it as its primary outcome.

This layer is implemented as deterministic policy-based AI/ML-assisted decisioning rather than an LLM-based autonomous agent.

---

### 4. Recovery Strategy Optimization

After the recovery decision is generated, RecoverAI evaluates candidate recovery strategies through an optimization layer.

The optimization pipeline includes:

- Candidate action generation
- Fitness-based scoring
- Metaheuristic optimization
- Quantum-inspired classical scoring
- Guardrail evaluation

The optimizer combines the base fitness score with a quantum-inspired score to select the highest-scoring valid recovery strategy.

The quantum-inspired component uses classical mathematical computation. It does **not** require a quantum computer.

---

### 5. Safety Guardrails

Safety and business constraints are applied before recovery execution.

The guardrail and execution validation layers help prevent:

- Invalid recovery actions
- Unsafe retry attempts
- Exceeding retry limits
- Payment and optimization mismatches
- Execution of non-approved actions
- Use of stale optimization results
- Duplicate recovery execution
- Execution of blocked strategies

Every recovery execution is validated against the approved optimization and guardrail state before it can proceed.

---

### 6. Controlled Recovery Execution

The current prototype operates in:

**Simulation Mode**

This means:

- No real customer payment is retried
- No real payment link is created through an external payment API
- No real customer communication is sent
- No real money movement is performed

The execution layer records the recovery attempt and its result, allowing the complete recovery workflow to be demonstrated safely.

A sandbox execution mode is represented in the architecture, but the current prototype intentionally blocks it unless properly configured.

---

## End-to-End Workflow

```text
                         FAILED PAYMENT
                               |
                               v
                  +--------------------------+
                  | Payment API / Razorpay   |
                  | Webhook Ingestion         |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Payment Persistence      |
                  | & Validation             |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | ML Recovery Prediction   |
                  | Logistic Regression      |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Recovery Decision Engine |
                  | Policy + Retry Limits    |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Candidate Generation     |
                  | & Optimization           |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Quantum-Inspired         |
                  | Classical Scoring        |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Safety Guardrails         |
                  | & Validation              |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Recovery Execution        |
                  | Simulation Mode           |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  | Dashboard & Audit Logs    |
                  +--------------------------+
