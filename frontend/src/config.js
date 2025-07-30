// API Configuration for different environments
const config = {
  // When running locally with proxy
  development: {
    apiBaseUrl: 'http://localhost:5003', // Connect directly to backend temporarily
  },
  // When deployed via ngrok (frontend served statically, backend proxied)
  production: {
    apiBaseUrl: '', // Use relative URLs with proxy - ngrok will proxy to backend
  }
};

// Always use empty string to leverage the proxy configuration
const currentConfig = config.development; // Always use proxy approach

export const API_BASE_URL = currentConfig.apiBaseUrl;
export default currentConfig; 