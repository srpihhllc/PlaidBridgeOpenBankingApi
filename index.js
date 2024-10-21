const express = require('express');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const cors = require('cors');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(morgan('combined'));
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Rate Limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use(limiter);

// Routes
app.get('/', (req, res) => {
  res.send('Welcome to PlaidBridgeOpenBankingApi!');
});

// Error and Maintenance Pages
app.use((req, res, next) => {
  res.status(404).sendFile(__dirname + '/public/error.html');
});

const maintenanceMode = (req, res, next) => {
  res.status(503).sendFile(__dirname + '/public/maintenance.html');
};

// Uncomment this line to enable maintenance mode
// app.use(maintenanceMode);

// Start server
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
