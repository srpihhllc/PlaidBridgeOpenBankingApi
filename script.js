import process from 'node:process';
import dotenv from 'dotenv';
import axios from 'axios';
import fs, { createReadStream } from 'fs';
import csv from 'csv-parser';
import { createObjectCsvWriter } from 'csv-writer';
import { addDays, format } from 'date-fns';
import path from 'path';

dotenv.config();

// Set up API credentials as variables
const apiKey = process.env.API_KEY;
const apiSecret = process.env.API_SECRET;
const accountNumber = process.env.ACCOUNT_NUMBER;
const plaidClientId = process.env.PLAID_CLIENT_ID;
const plaidSecret = process.env.PLAID_SECRET;
const plaidPublicKey = process.env.PLAID_PUBLIC_KEY;

// Function to sanitize and validate input paths
function sanitizePath(inputPath) {
  const safeBasePath = path.resolve(__dirname, 'safe_directory');
  const resolvedPath = path.resolve(safeBasePath, inputPath);
  if (!resolvedPath.startsWith(safeBasePath)) {
    throw new Error('Invalid path');
  }
  return resolvedPath;
}

// Function to read CSV file and retrieve statements
async function readStatementsFromCsv(filePath) {
  try {
    const sanitizedPath = sanitizePath(filePath);
    const statements = [];
    return new Promise((resolve, reject) => {
      createReadStream(sanitizedPath)
        .pipe(csv())
        .on('data', (row) => {
          statements.push({
            date: row.date,
            description: row.description,
            amount: parseFloat(row.amount)
          });
        })
        .on('end', () => resolve(statements))
        .on('error', (error) => {
          console.error("Error reading CSV:", error);
          reject(error);
        });
    });
  } catch (error) {
    console.error("Invalid file path:", error);
    throw error;
  }
}

// Function to save statements as CSV files
async function saveStatementsAsCsv(statements, filename) {
  try {
    const sanitizedPath = sanitizePath(filename);
    const csvWriterInstance = createObjectCsvWriter({
      path: sanitizedPath,
      header: Object.keys(statements[0]).map(key => ({ id: key, title: key }))
    });
    await csvWriterInstance.writeRecords(statements);
    console.log(`Statements saved as '${filename}'.`);
  } catch (error) {
    console.error(`Error saving statements as CSV: ${error}`);
    throw error;
  }
}

// Additional functions...

