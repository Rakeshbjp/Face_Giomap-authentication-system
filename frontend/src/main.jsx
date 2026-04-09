import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import 'leaflet/dist/leaflet.css';
import './index.css';
import { ClerkProvider } from '@clerk/react';

ReactDOM.createRoot(document.getElementById('root')).render(
  <ClerkProvider afterSignOutUrl="/">
    <App />
  </ClerkProvider>
);
