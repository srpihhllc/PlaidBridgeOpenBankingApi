# PlaidBridgeOpenBankingApi

## Description
A Python project integrating with Plaid’s API to support Open Banking functionalities.

## Installation

1. Clone the repo:
    ```sh
    git clone https://github.com/srpihhllc/PlaidBridgeOpenBankingApi
    cd PlaidBridgeOpenBankingApi
    ```

2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up environment variables:
    - Create a `.env` file in the root directory and add the following variables:
      ```env
      REDIS_URL=your_redis_url
      MOCK_USERNAME=srpollardsihhllc@gmail.com
      MOCK_PASSWORD=your_2Late2little$
      USER_EMAIL=your_srpollardsihhllc@gmail.com
      USER_PASSWORD=your_skeeMdralloP1$t
      JWT_SECRET=your_wiwmU1jZdt+uWOsmoaywjCVXgxaAZbBuOY7HqQt2ydY=
      ```

## Running the Application

1. Start the Flask application:
    ```sh
    python app.py
    ```

2. The application will run on `http://localhost:3000`.

## Endpoints

- **Manual Login:** `POST /manual-login`
- **Micro Deposits:** `POST /micro-deposits`
- **Actual Deposits:** `POST /actual-deposits`
- **Transfer Funds:** `POST /transfer-funds`
- **Open Banking:** `POST /open-banking`
- **Upload PDF:** `POST /upload-pdf`

## License

This project is licensed under a proprietary license. All rights reserved.

