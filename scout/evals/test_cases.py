"""
Test cases for evaluating Scout.

Each test case includes:
- question: The natural language question to ask
- expected_strings: Strings that should appear in the response (for backward compatibility)
- category: Test category for filtering
- golden_path: Optional file path where the answer should be found

When golden_path is provided, the evaluation will:
1. Verify the agent cited the correct source document
2. Factor source citation into the pass/fail decision
"""

from dataclasses import dataclass


@dataclass
class TestCase:
    """A test case for evaluating Scout."""

    question: str
    expected_strings: list[str]
    category: str
    golden_path: str | None = None


# Test cases organized by category
TEST_CASES: list[TestCase] = [
    # Policy - questions about company policies and HR
    TestCase(
        question="What is our PTO policy?",
        expected_strings=["unlimited", "manager approval", "two weeks", "Workday"],
        category="policy",
        golden_path="company-docs/policies/employee-handbook.md",
    ),
    TestCase(
        question="How much parental leave do we offer?",
        expected_strings=["16 weeks", "fully paid"],
        category="policy",
        golden_path="company-docs/policies/employee-handbook.md",
    ),
    TestCase(
        question="What is our remote work policy?",
        expected_strings=["hybrid", "two days", "Tuesday", "Thursday"],
        category="policy",
        golden_path="company-docs/policies/employee-handbook.md",
    ),
    TestCase(
        question="What medical plans do we offer?",
        expected_strings=["PPO Gold", "PPO Silver", "HDHP"],
        category="policy",
        golden_path="company-docs/hr/benefits-guide.md",
    ),
    TestCase(
        question="What is our 401k match?",
        expected_strings=["4%", "Fidelity"],
        category="policy",
        golden_path="company-docs/hr/benefits-guide.md",
    ),
    # Runbook - engineering operations questions
    TestCase(
        question="How do I deploy to production?",
        expected_strings=["blue-green", "deploy.internal.acme.io"],
        category="runbook",
        golden_path="engineering-docs/runbooks/deployment.md",
    ),
    TestCase(
        question="What is the SLA for SEV1 incidents?",
        expected_strings=["5 minutes", "1 hour"],
        category="runbook",
        golden_path="engineering-docs/runbooks/incident-response.md",
    ),
    TestCase(
        question="What is the rollback procedure?",
        expected_strings=["p99", "800ms", "error rate", "1%"],
        category="runbook",
        golden_path="engineering-docs/runbooks/deployment.md",
    ),
    TestCase(
        question="How does the on-call rotation work?",
        expected_strings=["PagerDuty", "Monday", "7 days"],
        category="runbook",
        golden_path="engineering-docs/runbooks/oncall-guide.md",
    ),
    TestCase(
        question="What happens when a high API latency alert fires?",
        expected_strings=["800ms", "connection pool", "kubectl"],
        category="runbook",
        golden_path="engineering-docs/runbooks/oncall-guide.md",
    ),
    # Navigation - requires multi-hop search or cross-document reasoning
    TestCase(
        question="What MFA methods are approved?",
        expected_strings=["YubiKey", "Okta Verify"],
        category="navigation",
        golden_path="company-docs/policies/security-policy.md",
    ),
    TestCase(
        question="What is the professional development budget?",
        expected_strings=["3,000", "$3,000"],
        category="navigation",
        golden_path="company-docs/policies/employee-handbook.md",
    ),
    TestCase(
        question="How do I report a security incident?",
        expected_strings=["#security", "security@"],
        category="navigation",
        golden_path="company-docs/policies/security-policy.md",
    ),
    TestCase(
        question="What are our company OKRs?",
        expected_strings=["Q4", "2024"],
        category="navigation",
        golden_path="company-docs/planning/q4-2024-okrs.md",
    ),
    # Edge cases - ambiguous, not found, or boundary conditions
    TestCase(
        question="What is the pet policy?",
        expected_strings=["not", "pet"],
        category="edge_case",
        # Should acknowledge the topic and indicate nothing was found
    ),
    TestCase(
        question="Who is the CEO of Acme Corp?",
        expected_strings=["not", "CEO"],
        category="edge_case",
        # Should acknowledge the topic and indicate nothing was found
    ),
    TestCase(
        question="What is the data retention policy for customer PII?",
        expected_strings=["data-retention", "retention"],
        category="edge_case",
        golden_path="company-docs/policies/data-retention.md",
    ),
]

# Categories for filtering
CATEGORIES = ["policy", "runbook", "navigation", "edge_case"]
