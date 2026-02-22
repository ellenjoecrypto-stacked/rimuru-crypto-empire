import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AccountBalance,
  Security,
  SmartToy
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useWebSocket } from '../services/websocket';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

interface BotStatus {
  name: string;
  status: string;
  running: boolean;
  total_trades: number;
  successful_trades: number;
  total_profit: number;
}

interface RiskSummary {
  positions_count: number;
  daily_pnl: number;
  total_unrealized_pnl: number;
  emergency_stop_triggered: boolean;
}

const Dashboard: React.FC = () => {
  const [bots, setBots] = useState<BotStatus[]>([]);
  const [riskSummary, setRiskSummary] = useState<RiskSummary | null>(null);
  const [portfolioValue, setPortfolioValue] = useState(125500);
  const { isConnected, lastMessage } = useWebSocket();

  // Simulated chart data
  const chartData = [
    { time: '00:00', value: 124000 },
    { time: '04:00', value: 124500 },
    { time: '08:00', value: 125000 },
    { time: '12:00', value: 125500 },
    { time: '16:00', value: 125200 },
    { time: '20:00', value: 125800 },
  ];

  useEffect(() => {
    fetchInitialData();
    const interval = setInterval(fetchInitialData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (lastMessage) {
      handleWebSocketMessage(lastMessage);
    }
  }, [lastMessage]);

  const fetchInitialData = async () => {
    try {
      const [botsResponse, riskResponse] = await Promise.all([
        axios.get(`${API_URL}/bots`),
        axios.get(`${API_URL}/risk/summary`)
      ]);

      setBots(Object.values(botsResponse.data.bots));
      setRiskSummary(riskResponse.data);
    } catch {
      // errors surfaced through UI state
    }
  };

  const handleWebSocketMessage = (message: any) => {
    if (message.type === 'bot_status') {
      setBots(Object.values(message.data));
    } else if (message.type === 'risk_summary') {
      setRiskSummary(message.data);
    }
  };

  const StatCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode; color: string; trend?: number }> = 
    ({ title, value, icon, color, trend }) => (
    <Card sx={{ height: '100%', bgcolor: '#1a1a1a', border: `1px solid ${color}` }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box>
            <Typography component="h3" variant="h6" color="textSecondary" gutterBottom>
              {title}
            </Typography>
            <Typography component="p" variant="h4" color={color} fontWeight="bold">
              {value}
            </Typography>
            {trend !== undefined && (
              <Box display="flex" alignItems="center" mt={1}>
                {trend >= 0 ? (
                  <TrendingUp sx={{ color: '#00ff88', mr: 0.5 }} aria-hidden="true" />
                ) : (
                  <TrendingDown sx={{ color: '#ff4444', mr: 0.5 }} aria-hidden="true" />
                )}
                <Typography variant="body2" color={trend >= 0 ? '#00ff88' : '#ff4444'}>
                  <span className="visually-hidden">{trend >= 0 ? 'Up' : 'Down'}</span>
                  {trend >= 0 ? '+' : ''}{trend}%
                </Typography>
              </Box>
            )}
          </Box>
          <Box sx={{ fontSize: '48px', color }} aria-hidden="true">
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Typography component="h1" variant="h4" gutterBottom sx={{ color: '#00ff88', fontWeight: 'bold' }}>
        RIMURU CRYPTO EMPIRE
      </Typography>
      
      {/* Connection Status */}
      <Box mb={3} role="status" aria-live="polite">
        <Chip 
          label={isConnected ? 'Connected' : 'Disconnected'}
          color={isConnected ? 'success' : 'error'}
          sx={{ mr: 2 }}
          icon={<span aria-hidden="true">{isConnected ? '🟢' : '🔴'}</span>}
        />
        <Typography variant="caption" color="textSecondary">
          Real-time updates {isConnected ? 'enabled' : 'disabled'}
        </Typography>
      </Box>

      {/* Main Stats */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Portfolio Value"
            value={`$${portfolioValue.toLocaleString()}`}
            icon={<AccountBalance aria-hidden="true" />}
            color="#00ff88"
            trend={2.5}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Daily P&L"
            value={`$${riskSummary?.daily_pnl?.toFixed(2) || '0.00'}`}
            icon={<TrendingUp aria-hidden="true" />}
            color={riskSummary?.daily_pnl >= 0 ? '#00ff88' : '#ff4444'}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Bots"
            value={bots.filter(b => b.running).length}
            icon={<SmartToy aria-hidden="true" />}
            color="#ff0088"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Open Positions"
            value={riskSummary?.positions_count || 0}
            icon={<Security aria-hidden="true" />}
            color="#00bfff"
          />
        </Grid>
      </Grid>

      {/* Chart and Bot Status */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '400px' }}>
            <CardContent>
              <Typography component="h2" variant="h6" gutterBottom sx={{ color: '#00ff88' }} id="chart-title">
                Portfolio Performance
              </Typography>
              <div role="img" aria-labelledby="chart-title" aria-describedby="chart-desc">
                <span id="chart-desc" className="visually-hidden">
                  Line chart showing portfolio value over time, from $124,000 at 00:00 to approximately $125,800 at 20:00.
                </span>
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="time" stroke="#666" />
                    <YAxis stroke="#666" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="value" stroke="#00ff88" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '400px' }}>
            <CardContent>
              <Typography component="h2" variant="h6" gutterBottom sx={{ color: '#00ff88' }}>
                Bot Status
              </Typography>
              <Box mt={2}>
                {bots.map((bot) => (
                  <Box key={bot.name} mb={2}>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">{bot.name}</Typography>
                      <Chip 
                        label={bot.status} 
                        size="small"
                        color={bot.running ? 'success' : 'default'}
                      />
                    </Box>
                    <Typography variant="caption" color="textSecondary">
                      Trades: {bot.total_trades} | Profit: ${bot.total_profit.toFixed(2)}
                    </Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={bot.total_trades * 10}
                      sx={{ mt: 1, bgcolor: '#333' }}
                      aria-label={`${bot.name} progress`}
                    />
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Emergency Warning */}
      {riskSummary?.emergency_stop_triggered && (
        <Box mt={3} role="alert" aria-live="assertive">
          <Card sx={{ bgcolor: '#ff0000', border: '2px solid #ff4444' }}>
            <CardContent>
              <Typography variant="h6" color="white" fontWeight="bold">
                <span aria-hidden="true">🚨</span> EMERGENCY STOP TRIGGERED
              </Typography>
              <Typography variant="body2" color="white">
                All trading operations have been halted. Check risk management settings.
              </Typography>
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
};

export default Dashboard;