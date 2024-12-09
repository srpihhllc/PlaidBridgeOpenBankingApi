# PlaidBridgeOpenBankingAPI

## Overview

This project is a user-friendly web application that allows users to upload PDF statements, parse them, and generate CSV and PDF files. It integrates with the Plaid API for financial data and Treasury Prime API for account verification.

## Prerequisites

Ensure you have the following installed locally:

- [Python 3.8+](https://www.python.org/downloads/)
- [Node.js with npm (18.17.1+)](https://nodejs.org/)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Azure Functions Core Tools (4+)](https://docs.microsoft.com/azure/azure-functions/functions-run-local)

## Setup and Run Locally

### Backend (Flask API)

1. **Clone the repository:**

    ```sh
    git clone https://github.com/your-repo/plaidbridgeopenbankingapi.git
    cd plaidbridgeopenbankingapi
    ```

2. **Set up the environment variables:**

    Create a `.env` file in the root directory with the following content:

    ```env
    PORT=3000
    PLAID_CLIENT_ID=your_plaid_client_id
    PLAID_SECRET=your_plaid_secret
    TREASURY_PRIME_API_KEY=your_treasury_prime_api_key
    TREASURY_PRIME_API_URL=your_treasury_prime_api_url
    ```

3. **Install dependencies:**

    ```sh
    pip install -r requirements.txt
    ```

4. **Run the Flask API:**

    ```sh
    python app.py
    ```

    The API will be available at [http://localhost:3000](http://localhost:3000).

### Frontend (React App)

1. **Navigate to the frontend directory:**

    ```sh
    cd src/web
    ```

2. **Set up the environment variables:**

    Create a `.env` file in the  directory with the following content:

    ```env
    REACT_APP_API_BASE_URL=http://localhost:3000
    ```

3. **Install dependencies:**

    ```sh
    npm install
    ```

4. **Run the React app:**

    ```sh
    npm start
    ```

    Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

## Deploy to Azure

### Backend (Flask API)

1. **Log in to Azure:**

    ```sh
    az login
    ```

2. **Create an Azure Function App:**

    ```sh
    az functionapp create --resource-group your-resource-group --consumption-plan-location your-location --runtime python --functions-version 3 --name your-function-app-name --storage-account your-storage-account
    ```

3. **Deploy the Flask API to Azure Functions:**

    ```sh
    func azure functionapp publish your-function-app-name
    ```

### Frontend (React App)

1. **Deploy the React app to Azure Static Web Apps:**

    Follow the [Azure Static Web Apps documentation](https://docs.microsoft.com/en-us/azure/static-web-apps/getting-started?tabs=react) to deploy your React app.

## API Endpoints

- **`GET /`**: Render the index page.
- **`POST /upload-pdf`**: Upload and process a PDF file.
- **`GET /statements/<filename>`**: Download a processed statement.
- **`GET /generate-pdf/<csv_filename>`**: Generate a PDF from a CSV file.

## Learn More

You can learn more in the [Flask documentation](https://flask.palletsprojects.com/en/2.0.x/).

To learn React, check out the [React documentation](https://reactjs.org/).

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit https://cla.microsoft.com.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## License

Proprietary License

All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.

© [Sir Pollards Internal Holistic Healing LLC/Terence Pollard Sr.] [2024]

   
       
        

                
  
       


        

        
    
       
