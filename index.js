
// Function to receive verification code from Piermont
function receiveVerificationCode() {
    // Simulate receiving the verification code                                              
    const verificationCode = 'received_verification_code';
    return verificationCode;
}

// Function to generate access token using verification code


// Function to retrieve bank statements from mock database
function retrieveStatements() {
    const mockStatements = [
        { date: '2024-04-01', description: 'Transaction 1', amount: 100.00 },
        { date: '2024-04-15', description: 'Transaction 2', amount: 200.00 },
        { date: '2024-05-01', description: 'Transaction 3', amount: 150.00 },
        { date: '2024-06-01', description: 'Transaction 4', amount: 250.00 },
        { date: '2024-07-01', description: 'Transaction 5', amount: 300.00 },
        { date: '2024-08-01', description: 'Transaction 6', amount: 350.00 },
    ];
    return mockStatements;
}

// Function to save statements as CSV files
function saveStatementsAsCsv(statements, filename) {
    const csvWriterInstance = csvWriter({
        path: filename,
        header: Object.keys(statements[0]).map(key => ({ id: key, title: key }))
    });
    csvWriterInstance.writeRecords(statements)
        .then(() => console.log(`Statements saved as '${filename}'.`));
}

// Function to handle manual login, verification, and bank account linking
async function manualLoginAndLinkBankAccount() {
    // Simulate manual login process
    console.log("Lender logs in manually.");
    
    // Simulate verification process
    console.log("Lender is verified.");
    
    // Provide voided check for account verification
    console.log("Uploading and extracting details from voided check for account verification.");
    
    // Simulate extracting details from voided check
    const extractedAccountNumber = '7030 3429 9651';  // Replace with extracted account number
    const extractedRoutingNumber = '026 015 053';  // Replace with extracted routing number
    console.log(`Extracted Account Number: ${extractedAccountNumber}`);
    console.log(`Extracted Routing Number: ${extractedRoutingNumber}`);
    
    // Receive verification code
    const verificationCode = receiveVerificationCode();
    
    // Generate access token
    const accessToken = await generateAccessToken(verificationCode);
    
    // Bank verification step
    console.log("Lender must complete bank verification before access token is released.");
    const bankVerified = true;  // Simulate bank verification process
    
    if (bankVerified) {
        // Share access token with the lender
        console.log(`Share this access token with the lender: ${accessToken}`);
        console.log("User email: srpollardsihhllc@gmail.com");
        console.log("User password: 2Late2little$");
        
        // Retrieve and provide access to CSV files
        const statements = retrieveStatements();
        console.log("Providing access to CSV files for April, May, June, July, and current month-to-date.");
        saveStatementsAsCsv(statements, 'statements.csv');
        
        // Navigation instructions for the lender
        console.log("To access the statements, please follow these steps:");
        console.log("1. Log in to the Found banking interface.");
        console.log("2. Navigate to the 'Statements' section.");
        console.log("3. Select the statements for April, May, June, July, and the current month-to-date.");
        console.log("4. Download the statements in CSV format.");
    } else {
        console.log("Bank verification failed. Access token will not be released.");
    }
}

// Example usage
manualLoginAndLinkBankAccount();

// Mock the API endpoint
nock('https://api.sandbox.treasuryprime.com')
  .post('/verification')
  .reply(200, { access_token: 'mock_access_token' });

// Test the generateAccessToken function
async function testGenerateAccessToken() {
  const verificationCode = 'mock_verification_code';
  const accessToken = await generateAccessToken(verificationCode);
  console.log('Mock Access Token:', accessToken);
}

// Run the test
testGenerateAccessToken()
