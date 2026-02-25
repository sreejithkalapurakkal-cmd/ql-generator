import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 429) {
      console.error('Rate limited. Please wait before retrying.');
    } else if (status && status >= 500) {
      console.error('Server error. Please try again later.');
    } else if (status === 404) {
      console.error('Resource not found.');
    } else if (!error.response) {
      console.error('Network error. Check your connection.');
    }
    return Promise.reject(error);
  }
);

export default api;
