const express = require('express');
const helmet = require('helmet');
const app = express();
const port = process.env.PORT || 3000;

// Use Helmet to set security headers
app.use(helmet({
  contentSecurityPolicy: false,
  frameguard: {
    action: 'deny'
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true
  }
}));

// Middleware function
function normalizeDirectives(rawDirectives) {
  const normalizedDirectives = {};
  for (const rawDirectiveName in rawDirectives) {
    if (Object.prototype.hasOwnProperty.call(rawDirectives, rawDirectiveName)) {
      normalizedDirectives[rawDirectiveName.toLowerCase()] = rawDirectives[rawDirectiveName];
    }
  }
  return normalizedDirectives;
}

// Sample route
app.get('/', (req, res) => {
  res.send('Hello, world!');
});

// Start the server
app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});


