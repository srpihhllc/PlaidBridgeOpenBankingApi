"scripts": {
    "start": "node script.js"
  },
  "dependencies": {
    "axios": "^0.21.1",
    "dotenv": "^8.2.0",
    "csv-parser": "^2.3.3",
    "csv-writer": "^1.6.0",
    "express": "^4.18.2",
    "express-rate-limit": "^6.3.0",
    "helmet": "^5.0.4",
    "cors": "^2.8.5",
    "celebrate": "^17.0.0",
    "joi": "^17.8.0",
    "jsonwebtoken": "^9.0.0",
    "winston": "^3.8.2",
    "morgan": "^1.10.0",
    "redis": "^4.6.6",
    "util": "^0.12.4",
    "nock": "^13.0.0"
  },
  "extendedDescription": {
    "features": [
      "API Integration (axios)",
      "CSV Handling",
      "Statements Retrieval",
      "Manual Login & Verification"
    ],
    "setup": [
      "Clone the repo.",
      "Create a `.env` file.",
      "Install dependencies: `npm install`."
    ],
    "usage": "Run: `node script.js`"
  }
