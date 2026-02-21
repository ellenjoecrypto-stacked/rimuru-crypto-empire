import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Dashboard from './components/Dashboard';
import Trading from './components/Trading';
import Bots from './components/Bots';
import Security from './components/Security';
import AccountSettings from './components/AccountSettings';
import Navigation from './components/Navigation';
import { WebSocketProvider } from './services/websocket';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00ff88',
    },
    secondary: {
      main: '#ff0088',
    },
    background: {
      default: '#0a0a0a',
      paper: '#1a1a1a',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <WebSocketProvider>
        <Router>
          <div style={{ display: 'flex' }}>
            <Navigation />
            <main style={{ flexGrow: 1, padding: '20px' }}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/trading" element={<Trading />} />
                <Route path="/bots" element={<Bots />} />
                <Route path="/security" element={<Security />} />
                <Route path="/settings" element={<AccountSettings />} />
              </Routes>
            </main>
          </div>
        </Router>
      </WebSocketProvider>
    </ThemeProvider>
  );
}

export default App;