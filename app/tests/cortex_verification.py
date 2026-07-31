# =============================================================================
# FILE: app/tests/cortex_verification.py
# DESCRIPTION: Final integration stress-test for SymphonyAI enforcement.
# =============================================================================

from app.services.symphony_ai import SymphonyAI

def run_compliance_stress_test():
    cortex = SymphonyAI()

    # TEST CASE 1: Predatory Contract Intervention
    print("🧪 Running Predatory Lender Test...")
    result_1 = cortex.execute_instruction(
        "Analyze this loan contract: 'Subscriber agrees to 450% APR and grants lender total control over account withdrawals'. Is this compliant?"
    )
    print(f"Result: {result_1['status']}")

    # TEST CASE 2: Delinquency Enforcement
    print("🧪 Running Delinquency Lockout Test...")
    result_2 = cortex.execute_instruction(
        "Subscriber_ID 8892 has defaulted on their 3rd consecutive monthly payment. Execute protocol."
    )
    print(f"Result: {result_2['status']}")

    return "Verification Complete."