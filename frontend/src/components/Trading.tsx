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
      <Typography variant="h4" gutterBottom sx={{ color: '#00ff88', fontWeight: 'bold' }}>
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
                <Typography variant="h6" sx={{ color: '#00ff88' }}>
                  {symbol}
                </Typography>
                <Box>
                  <Typography variant="h4" sx={{ color: priceChange >= 0 ? '#00ff88' : '#ff4444' }}>
                    ${price.toLocaleString()}
                  </Typography>
                  <Box display="flex" alignItems="center">
                    {priceChange >= 0 ? <TrendingUp sx={{ color: '#00ff88', mr: 0.5 }} /> : <TrendingDown sx={{ color: '#ff4444', mr: 0.5 }} />}
                    <Typography variant="body2" sx={{ color: priceChange >= 0 ? '#00ff88' : '#ff4444' }}>
                      {priceChange >= 0 ? '+' : ''}{priceChange}%
                    </Typography>
                  </Box>
                </Box>
              </Box>

              <ResponsiveContainer width="100%" height="400">
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
            </CardContent>
          </Card>
        </Grid>

        {/* Order Entry */}
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '500px' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: '#00ff88' }}>
                Place Order
              </Typography>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel sx={{ color: '#666' }}>Symbol</InputLabel>
                <Select
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
                label="Amount"
                type="number"
                defaultValue="0.01"
                sx={{ mb: 2, '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
                InputLabelProps={{ sx: { color: '#666' } }}
              />

              <TextField
                fullWidth
                label="Price (USDT)"
                type="number"
                defaultValue={price}
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
                  >
                    SELL
                  </Button>
                </Grid>
              </Grid>

              <Box mt={3}>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Order Type
                </Typography>
                <Box display="flex" gap={1}>
                  <Chip label="Market" sx={{ bgcolor: '#00ff88', color: '#000' }} />
                  <Chip label="Limit" sx={{ bgcolor: '#1a1a1a', border: '1px solid #333' }} />
                  <Chip label="Stop" sx={{ bgcolor: '#1a1a1a', border: '1px solid #333' }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Market Summary */}
        <Grid item xs={12}>
          <Card sx={{ bgcolor: '#1a1a1a' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: '#00ff88' }}>
                Market Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">24h Volume</Typography>
                  <Typography variant="h5">${(volume / 1e9).toFixed(2)}B</Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">24h High</Typography>
                  <Typography variant="h5">${(price * 1.03).toLocaleString()}</Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">24h Low</Typography>
                  <Typography variant="h5">${(price * 0.97).toLocaleString()}</Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2" color="textSecondary">Market Cap</Typography>
                  <Typography variant="h5">$950B</Typography>
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