import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Alert
} from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const Trading: React.FC = () => {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [price, setPrice] = useState(50000);
  const [priceChange, setPriceChange] = useState(2.5);
  const [volume, setVolume] = useState(1234567890);
  const [orderType, setOrderType] = useState('market');
  const [amount, setAmount] = useState('0.01');
  const [limitPrice, setLimitPrice] = useState(String(50000));
  
  // Simulated chart data
  const chartData = [
    { time: '00:00', price: 49200 },
    { time: '04:00', price: 49500 },
    { time: '08:00', price: 49800 },
    { time: '12:00', price: 50000 },
    { time: '16:00', price: 50200 },
    { time: '20:00', price: 50000 },
  ];

  const handleTrade = (side: string) => {
    alert(`${side.toUpperCase()} order for ${symbol} would be executed here`);
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom sx={{ color: '#00ff88', fontWeight: 'bold' }}>
        Trading Interface
      </Typography>

      <Alert severity="warning" sx={{ mb: 3 }}>
        Paper trading mode enabled. No real funds are being used.
      </Alert>

      <Grid container spacing={3}>
        {/* Market Data */}
        <Grid item xs={12} md={8}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '500px' }}>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6" component="h2" sx={{ color: '#00ff88' }}>
                  {symbol}
                </Typography>
                <Box>
                  <div aria-live="polite" aria-atomic="true">
                    <Typography variant="h4" component="p" sx={{ color: priceChange >= 0 ? '#00ff88' : '#ff4444' }}>
                      ${price.toLocaleString()}
                    </Typography>
                  </div>
                  <Box display="flex" alignItems="center">
                    {priceChange >= 0 ? <TrendingUp sx={{ color: '#00ff88', mr: 0.5 }} aria-hidden="true" /> : <TrendingDown sx={{ color: '#ff4444', mr: 0.5 }} aria-hidden="true" />}
                    <Typography variant="body2" sx={{ color: priceChange >= 0 ? '#00ff88' : '#ff4444' }}>
                      {priceChange >= 0 ? '+' : ''}{priceChange}%
                      <span className="visually-hidden">{priceChange >= 0 ? ' (gain)' : ' (loss)'}</span>
                    </Typography>
                  </Box>
                </Box>
              </Box>

              <div role="img" aria-labelledby="trading-chart-title" aria-describedby="trading-chart-desc">
                <span id="trading-chart-title" className="visually-hidden">{symbol} Price Chart</span>
                <span id="trading-chart-desc" className="visually-hidden">
                  Line chart showing {symbol} price over 24 hours.
                </span>
                <ResponsiveContainer width="100%" height="400" aria-hidden="true">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="time" stroke="#666" />
                    <YAxis stroke="#666" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                    />
                    <Line type="monotone" dataKey="price" stroke="#00ff88" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </Grid>

        {/* Order Entry */}
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '500px' }}>
            <CardContent>
              <Typography variant="h6" component="h2" gutterBottom sx={{ color: '#00ff88' }}>
                Place Order
              </Typography>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel id="symbol-label" sx={{ color: '#666' }}>Symbol</InputLabel>
                <Select
                  labelId="symbol-label"
                  id="symbol-select"
                  value={symbol}
                  label="Symbol"
                  onChange={(e) => setSymbol(e.target.value)}
                  sx={{ bgcolor: '#0a0a0a' }}
                >
                  <MenuItem value="BTC/USDT">BTC/USDT</MenuItem>
                  <MenuItem value="ETH/USDT">ETH/USDT</MenuItem>
                  <MenuItem value="SOL/USDT">SOL/USDT</MenuItem>
                </Select>
              </FormControl>

              <TextField
                fullWidth
                id="order-amount"
                label="Amount"
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                sx={{ mb: 2, '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
                InputLabelProps={{ sx: { color: '#666' } }}
                inputProps={{ 'aria-required': 'true' }}
              />

              <TextField
                fullWidth
                id="order-price"
                label="Price (USDT)"
                type="number"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                sx={{ mb: 3, '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
                InputLabelProps={{ sx: { color: '#666' } }}
              />

              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="contained"
                    sx={{ 
                      bgcolor: '#00ff88', 
                      color: '#000', 
                      height: 60,
                      fontSize: '1.2rem',
                      fontWeight: 'bold',
                      '&:hover': { bgcolor: '#00cc6a' }
                    }}
                    onClick={() => handleTrade('buy')}
                    aria-label={`Buy ${symbol}`}
                  >
                    BUY
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="contained"
                    sx={{ 
                      bgcolor: '#ff4444', 
                      color: '#fff',
                      height: 60,
                      fontSize: '1.2rem',
                      fontWeight: 'bold',
                      '&:hover': { bgcolor: '#cc0000' }
                    }}
                    onClick={() => handleTrade('sell')}
                    aria-label={`Sell ${symbol}`}
                  >
                    SELL
                  </Button>
                </Grid>
              </Grid>

              <Box mt={3}>
                <Typography variant="body2" color="textSecondary" gutterBottom id="order-type-label">
                  Order Type
                </Typography>
                <Box display="flex" gap={1} role="group" aria-labelledby="order-type-label">
                  {(['market', 'limit', 'stop'] as const).map((type) => (
                    <Chip
                      key={type}
                      label={type.charAt(0).toUpperCase() + type.slice(1)}
                      role="button"
                      tabIndex={0}
                      aria-pressed={orderType === type}
                      onClick={() => setOrderType(type)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOrderType(type); } }}
                      sx={{ 
                        bgcolor: orderType === type ? '#00ff88' : '#1a1a1a', 
                        color: orderType === type ? '#000' : '#fff',
                        border: orderType === type ? 'none' : '1px solid #333',
                        cursor: 'pointer'
                      }}
                    />
                  ))}
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Market Summary */}
        <Grid item xs={12}>
          <Card sx={{ bgcolor: '#1a1a1a' }}>
            <CardContent>
              <Typography variant="h6" component="h2" gutterBottom sx={{ color: '#00ff88' }}>
                Market Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">24h Volume</Typography>
                  <Typography variant="h5" component="p">${(volume / 1e9).toFixed(2)}B</Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">24h High</Typography>
                  <Typography variant="h5" component="p">${(price * 1.03).toLocaleString()}</Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">24h Low</Typography>
                  <Typography variant="h5" component="p">${(price * 0.97).toLocaleString()}</Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">Market Cap</Typography>
                  <Typography variant="h5" component="p">$950B</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Trading;