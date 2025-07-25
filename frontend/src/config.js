// API Configuration for different environments
const config = {
  // When running locally with proxy
  development: {
    apiBaseUrl: '', // Use relative URLs with proxy
  },
  // When deployed via ngrok (frontend served statically, backend still local)
  production: {
    apiBaseUrl: 'http://localhost:5003', // Direct connection to local backend
  }
};

// Determine if we're in a tunneled/ngrok environment
const isNgrokDeployment = window.location.hostname.includes('ngrok') || 
                          window.location.hostname.includes('tunnel') ||
                          process.env.NODE_ENV === 'production';

const currentConfig = isNgrokDeployment ? config.production : config.development;

export const API_BASE_URL = currentConfig.apiBaseUrl;
export default currentConfig; 