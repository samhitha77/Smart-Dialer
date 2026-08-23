/**
 * Centralized API Service for SmartDialer Operations Dashboard.
 * Connects directly to FastAPI backend running at http://127.0.0.1:8000
 */

import axios from 'axios';

// The backend base URL - defaults to http://127.0.0.1:8000
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Response interceptor for standard error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    let message = 'An unexpected error occurred while communicating with the server.';
    
    if (error.response) {
      // Backend returned an error response (4xx, 5xx)
      if (error.response.data && error.response.data.detail) {
        message = typeof error.response.data.detail === 'string' 
          ? error.response.data.detail 
          : JSON.stringify(error.response.data.detail);
      } else if (error.response.status === 404) {
        message = 'The requested resource was not found on the server.';
      } else if (error.response.status >= 500) {
        message = 'Internal server error. Please verify backend logs.';
      }
    } else if (error.request) {
      // Request was made but no response was received (Network error/server down)
      message = 'Unable to connect to SmartDialer backend at ' + API_BASE_URL + '. Please ensure FastAPI is running.';
    }

    return Promise.reject(new Error(message));
  }
);

export const api = {
  // System Health
  getHealth: async () => {
    const res = await apiClient.get('/health');
    return res.data;
  },

  // Agents
  getAgents: async () => {
    const res = await apiClient.get('/agents/');
    return res.data;
  },

  getAvailableAgents: async () => {
    const res = await apiClient.get('/agents/available');
    return res.data;
  },

  createAgent: async (name) => {
    const res = await apiClient.post('/agents/', { name });
    return res.data;
  },

  transitionAgentState: async (agentId, targetState) => {
    const res = await apiClient.post(`/agents/${agentId}/transition?target_state=${encodeURIComponent(targetState)}`);
    return res.data;
  },

  // Borrowers
  getBorrowers: async () => {
    const res = await apiClient.get('/borrowers/');
    return res.data;
  },

  createBorrower: async (name, phoneNumber) => {
    const res = await apiClient.post('/borrowers/', {
      name,
      phone_number: phoneNumber,
    });
    return res.data;
  },

  // Calls
  getCalls: async () => {
    const res = await apiClient.get('/calls/');
    return res.data;
  },

  getCallStats: async () => {
    const res = await apiClient.get('/calls/stats');
    return res.data;
  },

  // Dialer
  runProgressiveCycle: async (provider = 'a') => {
    const res = await apiClient.post(`/dialer/progressive/cycle?provider=${encodeURIComponent(provider)}`);
    return res.data;
  },

  getPredictiveRecommendation: async (provider = 'a') => {
    const res = await apiClient.get(`/dialer/predictive/recommend?provider=${encodeURIComponent(provider)}`);
    return res.data;
  },

  // Events / Webhooks
  postProviderWebhook: async (eventId, providerCallId, eventType) => {
    const res = await apiClient.post('/events/provider-webhook', {
      event_id: eventId,
      provider_call_id: providerCallId,
      event_type: eventType,
    });
    return res.data;
  },

  getEvents: async () => {
    const res = await apiClient.get('/events/');
    return res.data;
  },
};

export default api;
