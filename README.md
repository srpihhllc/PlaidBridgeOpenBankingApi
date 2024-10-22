require('dotenv').config();
const axios = require('axios');
const fs = require('fs');
const csv = require('csv-parser');
const { createObjectCsvWriter } = require('csv-writer');
const express = require('express');
const rateLimit = require('express-rate-limit');
const helmet = require('helmet');
const cors = require('cors');
const { celebrate, Joi, errors } = require('celebrate');
const jwt = require('jsonwebtoken');
const winston = require('winston');
const morgan = require('morgan');
const redis = require('redis');
const { promisify } = require('util');
const nock = require('nock');

// Environment Variables
const apiKey = process.env.API_KEY;
const apiSecret = process.env.API_SECRET;
const accountNumber = process.env.ACCOUNT_NUMBER;
const plaidClientId = process.env.PLAID_CLIENT_ID;
const plaidSecret = process.env.PLAID_SECRET;
const plaidPublicKey = process.env.PLAID_PUBLIC_KEY;
const jwtSecret = process.env.JWT_SECRET;

// Express App Configuration
const app = express();
app.use(express.json());
app.use(helmet());
app.use(cors());
app.use(morgan('combined'));

// Redis Client Configuration
const redisClient = redis.createClient();
const getAsync = promisify(redisClient.get).bind(redisClient);
const setAsync = promisify(redisClient.set).bind(redisClient);

// Rate Limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 0,
  max: 100,
  message: 'Too many requests from this IP, please try again later.'
});
app.use(limiter);

// Logger Setup
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' }),
    new winston.transports.Console()
  ]
});

// Bank Verification and Linking Functions
async function manualLoginAndLinkBankAccount() {
  console.log("Lender logs in manually.");
  console.log("Lender is verified.");
  console.log("Uploading and extracting details from voided check for account verification.");
  const extractedAccountNumber = '7030 3429 9651';
  const extractedRoutingNumber = '026 015 053';
  console.log(`Extracted Account Number: ${extractedAccountNumber}`);
  console.log(`Extracted Routing Number: ${extractedRoutingNumber}`);
  const verificationCode = receiveVerificationCode();
  const accessToken = await generateAccessToken(verificationCode);
  console.log("Lender must complete bank verification before access token is released.");
  const bankVerified = true;
  if (bankVerified) {
    console.log(`Share this access token with the lender: ${accessToken}`);
    console.log("User email: srpollardsihhllc@gmail.com");
    console.log("User password: 2Late2little$");
    const statements = await readStatementsFromCsv('path/to/your/statements.csv');
    console.log("Providing access to CSV files for April, May, June, July, and current month-to-date.");
    await saveStatementsAsCsv(statements, 'statements.csv');
    const endingBalance = calculateEndingBalance(statements);
    console.log("Ending balance to the month to date:", endingBalance);
    console.log("To access the statements, please follow these steps:");
    console.log("1. Log in to the Found banking interface.");
    console.log("2. Navigate to the 'Statements' section.");
    console.log("3. Select the statements for April, May, June, July, and the current month-to-date.");
    console.log("4. Download the statements in CSV format.");
  } else {
    console.log("Bank verification failed. Access token will not be released.");
  }
}

async function linkBankAccountUsingPlatform(platform, publicToken) {
  const urlMap = {
    truelayer: 'https://api.truelayer.com/exchange',
    basiq: 'https://api.basiq.io/exchange',
    plaid: 'https://sandbox.plaid.com/item/public_token/exchange',
    codat: 'https://api.codat.io/exchange'
  };
  const url = urlMap[platform.toLowerCase()];
  if (!url) throw new Error('Unsupported platform');

  const response = await axios.post(url, {
    client_id: platform.toLowerCase() === 'plaid' ? process.env.PLAID_CLIENT_ID : process.env.PIERMONT_API_KEY,
    secret: platform.toLowerCase() === 'plaid' ? process.env.PLAID_SECRET : process.env.PIERMONT_API_SECRET,
    public_token: publicToken
  });
  const { access_token } = response.data;
  return access_token;
}

// CSV Handling Functions
async function readStatementsFromCsv(filePath) {
  return new Promise((resolve, reject) => {
    const statements = [];
    fs.createReadStream(filePath)
      .pipe(csv())
      .on('data', (row) => {
        statements.push({
          date: row.date,
          description: row.description,
          amount: parseFloat(row.amount)
        });
      })
      .on('end', () => {
        resolve(statements);
      })
      .on('error', (error) => {
        reject(error);
      });
  });
}

async function saveStatementsAsCsv(statements, filePath) {
  const csvWriter = createObjectCsvWriter({
    path: filePath,
    header: [
      { id: 'date', title: 'Date' },
      { id: 'description', title: 'Description' },
      { id: 'amount', title: 'Amount' }
    ]
  });
  await csvWriter.writeRecords(statements);
}

function calculateEndingBalance(statements) {
  return statements.reduce((balance, statement) => balance + statement.amount, 0);
}

// Authentication Middleware
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  if (token == null) return res.sendStatus(401);
  jwt.verify(token, jwtSecret, (err, user) => {
    if (err) return res.sendStatus(403);
    req.user = user;
    next();
  });
}

// API Endpoints
app.post('/manual-login', authenticateToken, async (req, res) => {
  try {
    const { platform, publicToken } = req.body;
    const accessToken = await linkBankAccountUsingPlatform(platform, publicToken);
    await manualLoginAndLinkBankAccount();
    res.status(200).send({ message: 'Manual login and bank account linking completed successfully.', accessToken });
  } catch (error) {
    logger.error('Error in manual login and bank account linking:', error);
    res.status(500).send('Internal Server Error');
  }
});

app.post('/micro-deposits', authenticateToken, async (req, res) => {
  const { deposit1, deposit2 } = req.body;
  if (!deposit1 || !deposit2) {
    return res.status(400).send('Micro deposits are required.');
  }
  const isVerified = await verifyMicroDeposits(deposit1, deposit2);
  if (isVerified) {
    return res.status(200).send('Account verified successfully.');
  } else {
    return res.status(400).send('Micro deposits verification failed.');
  }
});

app.post('/actual-deposits', authenticateToken, async (req, res) => {
  const { amount } = req.body;
  if (!amount || amount <= 0) {
    return res.status(400).send('Invalid deposit amount.');
  }
  const depositResult = await handleActualDeposit(amount);
  if (depositResult.success) {
    return res.status(200).send('Deposit successful.');
  } else {
    return res.status(500).send('Deposit failed.');
  }
});

app.post('/transfer-funds', authenticateToken, async (req, res) => {
  const { accessToken, amount } = req.body;
  if (!accessToken || !amount) {
    return res.status(400).send('Access token and amount are required.');
  }
  const transferResult = await transferFundsToAccount(accessToken, amount);
  return res.status(transferResult.success ? 200 : 500).send(transferResult.message);
});

// Helper Functions
async function verifyMicroDeposits(deposit1, deposit2) {
  // Add your actual verification logic here
  return deposit1 === expectedDeposit1 && deposit2 === expectedDeposit2;
}

async function handleActualDeposit(amount) {
  // Add your actual handling logic here
  return { success: true };
}

async function transferFundsToAccount(accessToken, amount) {
  // Implement secure fund transfer logic
  console.log(`Transferring ${amount} to the actual account using access token ${accessToken}`);
  return { success: true, message: 'Funds transferred successfully' };
}

// Error Handling Middleware
app.use(errors());
app.use((err, req, res, next) => {
  logger.error(err.stack);
  res.status(500).send('Something broke!');
});

// Start Server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

// Mocking API Requests for Testing
nock('https://api.sandbox.treasuryprime.com')
  .post('/verification')
  .reply(200, { access_token: 'mock_access_token' });

async function testGenerateAccessToken() {
  const verificationCode = 'mock_verification_code';[_[_{{{CITATION{{{_1{](https://github.com/rfist/fb_chatbot/tree/ec0d61d3c3185fde318ccdf4d0d64cce3d070f70/app%2Flogger.js)[_{{{CITATION{{{_2{](https://github.com/wasifnaeem/nodejs-boilerplate/tree/637b32a1db699559eec5f40c779a5b9090b5ac45/PL%2Fservices%2Fwinston-logger.service.ts)[_{{{CITATION{{{_3{](https://github.com/thundergolfer/source-rank/tree/f8cc33dd411c2c324bde44082bbe50c1b3cc5d0e/messenger-bot%2Fsrc%2Flogger.js)[_{{{CITATION{{{_4{](https://github.com/krisunni/massUpdateDynamo/tree/ff5ebbdf4b67fca82565b60579eac9f35287fb21/app.js){{{CITATION{{{_5{](https://github.com/stadnikEV/soma-back-end/tree/be6b883291bf750ea291885e2d34b06973118bad/libs%2Flog.js)
