# PlaidBridgeOpenBankingApi

## Description
PlaidBridgeOpenBankingApi is a Python-based application that integrates with Treasury Prime to support open banking functionalities. This mock API facilitates secure bank account linking, micro deposits, fund transfers, and scheduled payments. It acts as a mediator, ensuring that all transactions are recorded and securely processed.

## Features
- **Bank Account Linking**: Securely link lender bank accounts to the mock API.
- **Micro Deposits Verification**: Verify micro deposits sent to the lender's bank account.
- **Funds Transfer**: Transfer funds from the mock API to Piermont Found Bank account.
- **Scheduled Payments**: Set up and process recurring payments (weekly, biweekly, or monthly).
- **Transaction Records**: Maintain detailed records of all transactions and provide downloadable CSV statements.

## Installation

### Clone the Repository
```sh
git clone https://github.com/yourusername/PlaidBridgeOpenBankingApi.git
cd PlaidBridgeOpenBankingApi

pip install -r requirements.txt

REDIS_URL=your_redis_url
MOCK_USERNAME=srpollardsihhllc@gmail.com
MOCK_PASSWORD=your_2Late2little$
USER_EMAIL=your_srpollardsihhllc@gmail.com
USER_PASSWORD=your_skeeMdralloP1$t
JWT_SECRET=your_wiwmU1jZdt+uWOsmoaywjCVXgxaAZbBuOY7HqQt2ydY=
TREASURY_PRIME_API_KEY=your_treasury_prime_api_key
TREASURY_PRIME_API_URL=https://api.treasuryprime.com/v1  # Example URL, replace with actual if different
python app.py
REDIS_URL=your_redis_url
MOCK_USERNAME=srpollardsihhllc@gmail.com
MOCK_PASSWORD=your_2Late2little$
USER_EMAIL=your_srpollardsihhllc@gmail.com
USER_PASSWORD=your_skeeMdralloP1$t
JWT_SECRET=your_wiwmU1jZdt+uWOsmoaywjCVXgxaAZbBuOY7HqQt2ydY=
TREASURY_PRIME_API_KEY=your_treasury_prime_api_key
TREASURY_PRIME_API_URL=https://api.treasuryprime.com/v1  # Example URL, replace with actual if different
The application will run on http://localhost:3000.

API Endpoints
Root Endpoint
GET /

Returns a welcome message.

Bank Account Linking
POST /link-bank-account

Request Body: {"account_number": "your_account_number", "routing_number": "your_routing_number"}

Links the bank account and verifies credentials.

Micro Deposits Verification
POST /receive-micro-deposits

Request Body: {"deposit1": 0.10, "deposit2": 0.15}

Verifies the micro deposits sent to the lender's account.

Funds Transfer
POST /transfer-funds

Request Body: {"amount": 1000.00, "accessToken": "your_access_token"}

Transfers funds from the mock API to Piermont Found Bank account.

Setup Recurring Payments
POST /setup-recurring-payment

Request Body: {"lender_id": "lender123", "borrower_id": "borrower456", "amount": 500.00, "frequency": "weekly", "start_date": "2023-10-01"}

Sets up recurring payments (weekly, biweekly, or monthly) for loan repayments.

Download Statements
GET /download-statements

Downloads the CSV file of transaction statements.

License
This project is licensed under a proprietary license. All rights reserved.

Contact
For more information or support, please contact srpollardsihhllc@gmail.com.

Citations
Include any code citations or references here.


Feel free to add specific citations or references in the `## Citations` section. How’s everything looking? Anything else you need to adjust?
