import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import axios from 'axios';
import useNasoStore from './store/useNasoStore';

// Global Axios Interceptor for HTTP 401.
//
// `GET /users/me` is exempt: it is the session probe the app fires on every
// load, and a 401 from it is the expected answer for a browser with no cookie —
// not a session that just expired. Without the exemption, opening the login
// page fired a `POST /auth/logout` at the API before the operator had typed
// anything, and any 401 raced the restore path into clearing a session that was
// in the middle of being established.
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url ?? '';
    const isSessionProbe = url.endsWith('/users/me') && (error.config?.method ?? 'get').toLowerCase() === 'get';
    if (error.response && error.response.status === 401 && !isSessionProbe) {
      useNasoStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
