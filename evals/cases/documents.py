"""
Document Navigation Cases
=========================

Agent correctly navigates the enterprise document corpus in documents/.
Tests retrieval of policies, runbooks, architecture docs, and metrics.
Eval type: AccuracyEval (1-10 score)
"""

CASES: list[dict] = [
    {
        "input": "What is our PTO policy?",
        "expected_output": "Unlimited PTO with manager approval, minimum two weeks recommended. Found in the employee handbook under company-docs/policies/.",
        "guidelines": "Must mention unlimited PTO and manager approval. Should cite the source document.",
    },
    {
        "input": "How do I deploy to production?",
        "expected_output": "Blue-green deployment strategy via deploy.internal.acme.io. Found in engineering-docs/runbooks/deployment.md.",
        "guidelines": "Must mention blue-green deployment. Should reference the deployment runbook.",
    },
    {
        "input": "What is the SLA for SEV1 incidents?",
        "expected_output": "5 minutes to acknowledge, 1 hour to resolve for SEV1 incidents. Found in engineering-docs/runbooks/incident-response.md.",
        "guidelines": "Must include specific time targets for SEV1. Should reference incident response runbook.",
    },
    {
        "input": "What MFA methods are approved?",
        "expected_output": "YubiKey and Okta Verify are the approved MFA methods. Found in company-docs/policies/security-policy.md.",
        "guidelines": "Must mention at least one specific MFA method. Should reference the security policy.",
    },
    {
        "input": "What medical plans do we offer?",
        "expected_output": "PPO Gold, PPO Silver, and HDHP. Details in company-docs/hr/benefits-guide.md.",
        "guidelines": "Must list the medical plan options. Should reference the benefits guide.",
    },
    {
        "input": "What are our Q4 2024 OKRs?",
        "expected_output": "Q4 2024 objectives and key results found in company-docs/planning/q4-2024-okrs.md.",
        "guidelines": "Must reference actual OKR content. Should cite the planning document.",
    },
]
