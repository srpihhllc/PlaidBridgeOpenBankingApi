# =============================================================================
# FILE: app/agents/banking_tools.py
# DESCRIPTION: Finalized Gemini Function Declarations using google-genai.
#              Defines strict API contract between LLM and BankSimulator.
# =============================================================================

from google.genai import types

# 1. CORE FINANCIAL OPERATIONS
execute_deposit_tool = types.FunctionDeclaration(
    name="execute_deposit",
    description=(
        "Executes a simulated real-time cash deposit into a subscriber's "
        "account. Use this for valid ACH credits or lender escrow funding."
    ),
    parameters=types.Schema(
        type="object",
        properties={
            "subscriber_id": types.Schema(
                type="string",
                description=("The unique UUID of the subscriber account."),
            ),
            "amount": types.Schema(
                type="number",
                description="The positive float amount to deposit.",
            ),
            "memo": types.Schema(
                type="string",
                description=(
                    "Ledger description (e.g., 'ACH Transfer', 'Lender "
                    "Escrow')."
                ),
            ),
        },
        required=["subscriber_id", "amount", "memo"],
    ),
)

generate_statement_tool = types.FunctionDeclaration(
    name="generate_statement",
    description=(
        "Compiles automated analytics and generates a mock PDF financial "
        "statement."
    ),
    parameters=types.Schema(
        type="object",
        properties={
            "subscriber_id": types.Schema(
                type="string",
                description="The unique UUID of the subscriber.",
            ),
            "days": types.Schema(
                type="integer",
                description="The lookback period in days.",
            ),
        },
        required=["subscriber_id", "days"],
    ),
)

# 2. COMPLIANCE & ANTI-PREDATORY ENFORCEMENT
flag_predatory_lender_tool = types.FunctionDeclaration(
    name="flag_predatory_lender",
    description=(
        "CRITICAL: Invoke immediately if a contract contains predatory terms "
        "(usury, illegal penalties). Locks the lender and triggers a "
        "regulatory report."
    ),
    parameters=types.Schema(
        type="object",
        properties={
            "lender_id": types.Schema(
                type="string",
                description="The ID of the offending lender.",
            ),
            "violation_reason": types.Schema(
                type="string",
                description=(
                    "The specific regulatory statute violated (e.g., "
                    "FCRA/CFPB)."
                ),
            ),
            "contract_excerpt": types.Schema(
                type="string",
                description="The exact clause causing the violation.",
            ),
        },
        required=["lender_id", "violation_reason", "contract_excerpt"],
    ),
)

enforce_delinquency_lock_tool = types.FunctionDeclaration(
    name="enforce_delinquency_lock",
    description=(
        "Freezes a subscriber's account and halts all withdrawals when loan "
        "obligations are defaulted upon."
    ),
    parameters=types.Schema(
        type="object",
        properties={
            "subscriber_id": types.Schema(
                type="string",
                description="The ID of the delinquent subscriber.",
            ),
            "lock_reason": types.Schema(
                type="string",
                description=("Detailed explanation of the missed obligation."),
            ),
        },
        required=["subscriber_id", "lock_reason"],
    ),
)

# 3. TOOL BUNDLE FOR CORTEX INJECTION
FINANCIAL_CORTEX_TOOLS = [
    execute_deposit_tool,
    generate_statement_tool,
    flag_predatory_lender_tool,
    enforce_delinquency_lock_tool,
]
