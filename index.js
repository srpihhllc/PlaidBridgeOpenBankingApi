const helmet = require('helmet');

// Custom Middleware to Replace hasOwn
function normalizeDirectives(rawDirectives) {
  const normalizedDirectives = {};
  for (const rawDirectiveName in rawDirectives) {
    if (Object.prototype.hasOwnProperty.call(rawDirectives, rawDirectiveName)) {
      normalizedDirectives[rawDirectiveName.toLowerCase()] = rawDirectives[rawDirectiveName];
    }
  }
  return normalizedDirectives;
}

// Update Helmet usage
app.use(helmet({
  contentSecurityPolicy: false, // Example configuration
  frameguard: {
    action: 'deny'
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true
  }
}));
