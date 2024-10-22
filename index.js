const helmet = require('helmet');

// Middleware for setting security headers
app.use(helmet({
  contentSecurityPolicy: false, // Example of configuration
  frameguard: {
    action: 'deny'
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true
  }
}));

function normalizeDirectives(rawDirectives) {
  const normalizedDirectives = {};
  for (const rawDirectiveName in rawDirectives) {
    if (Object.prototype.hasOwnProperty.call(rawDirectives, rawDirectiveName)) {
      normalizedDirectives[rawDirectiveName.toLowerCase()] = rawDirectives[rawDirectiveName];
    }
  }
  return normalizedDirectives;
}

