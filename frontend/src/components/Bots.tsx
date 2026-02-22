import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  LinearProgress
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  Add,
  SmartToy,
  TrendingUp,
  Speed,
  Error as ErrorIcon
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

interface Bot {
  name: string;
  type: string;
  status: string;
  running: boolean;
  paused: boolean;
  total_trades: number;
  successful_trades: number;
  failed_trades: number;
  total_profit: number;
  started_at?: string;
  last_run?: string;
}

const Bots: React.FC = () => {
  const [bots, setBots] = useState<Bot[]>([]);
  const [open, setOpen] = useState(false);
  const [newBot, setNewBot] = useState({
    name: '',
    exchange: 'binance',
    symbol: 'BTC/USDT',
    strategy: 'rsi_reversal',
    paper_trading: true
  });
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open && firstInputRef.current) {
      firstInputRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    fetchBots();
    const interval = setInterval(fetchBots, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchBots = async () => {
    try {
      const response = await axios.get(`${API_URL}/bots`);
      setBots(Object.values(response.data.bots));
    } catch (error) {
      console.error('Error fetching bots:', error);
    }
  };

  const handleControlBot = async (name: string, action: string) => {
    try {
      await axios.post(`${API_URL}/bots/${name}/control`, { action });
      await fetchBots();
    } catch (error) {
      console.error('Error controlling bot:', error);
      alert(`Failed to ${action} bot`);
    }
  };

  const handleCreateBot = async () => {
    try {
      await axios.post(`${API_URL}/bots/create`, newBot);
      setOpen(false);
      await fetchBots();
      alert('Bot created successfully!');
    } catch (error) {
      console.error('Error creating bot:', error);
      alert('Failed to create bot');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return '#00ff88';
      case 'paused': return '#ffaa00';
      case 'stopped': return '#666';
      case 'error': return '#ff4444';
      default: return '#666';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <PlayArrow sx={{ fontSize: 14, mr: 0.5 }} aria-hidden="true" />;
      case 'paused': return <Pause sx={{ fontSize: 14, mr: 0.5 }} aria-hidden="true" />;
      case 'stopped': return <Stop sx={{ fontSize: 14, mr: 0.5 }} aria-hidden="true" />;
      case 'error': return <ErrorIcon sx={{ fontSize: 14, mr: 0.5 }} aria-hidden="true" />;
      default: return null;
    }
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ color: '#00ff88', fontWeight: 'bold' }}>
          Trading Bots
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add aria-hidden="true" />}
          sx={{ bgcolor: '#00ff88', color: '#000' }}
          onClick={() => setOpen(true)}
        >
          Create Bot
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        Create and manage automated trading bots. Start with paper trading to test strategies.
      </Alert>

      <Grid container spacing={3}>
        {bots.length === 0 ? (
          <Grid item xs={12}>
            <Card sx={{ bgcolor: '#1a1a1a', textAlign: 'center', py: 8 }}>
              <SmartToy sx={{ fontSize: 64, color: '#666', mb: 2 }} aria-hidden="true" />
              <Typography variant="h6" component="h2" color="textSecondary">
                No bots configured yet
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Create your first bot to start automated trading
              </Typography>
            </Card>
          </Grid>
        ) : (
          bots.map((bot) => (
            <Grid item xs={12} md={6} lg={4} key={bot.name}>
              <Card sx={{ 
                bgcolor: '#1a1a1a', 
                border: bot.running ? '2px solid #00ff88' : '1px solid #333',
                height: '100%'
              }}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
                    <Box>
                      <Typography variant="h6" component="h2" gutterBottom>
                        {bot.name}
                      </Typography>
                      <Chip
                        label={<>{getStatusIcon(bot.status)}{bot.status}</>}
                        size="small"
                        sx={{ bgcolor: getStatusColor(bot.status), color: '#000' }}
                      />
                    </Box>
                    <SmartToy sx={{ color: '#00ff88', fontSize: 32 }} aria-hidden="true" />
                  </Box>

                  <Box mb={2}>
                    <Typography variant="body2" color="textSecondary">
                      Strategy
                    </Typography>
                    <Typography variant="body1">
                      {bot.type.replace('_', ' ').toUpperCase()}
                    </Typography>
                  </Box>

                  <Box mb={2}>
                    <Typography variant="body2" color="textSecondary">
                      Performance
                    </Typography>
                    <Box display="flex" alignItems="center" mb={1}>
                      <TrendingUp sx={{ color: '#00ff88', mr: 1, fontSize: 16 }} aria-hidden="true" />
                      <Typography variant="h6" component="p" color="#00ff88">
                        ${bot.total_profit.toFixed(2)}
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="textSecondary">
                      Trades: {bot.total_trades} | Success: {bot.successful_trades}
                    </Typography>
                  </Box>

                  <Box mb={2}>
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      Win Rate
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={bot.total_trades > 0 ? (bot.successful_trades / bot.total_trades) * 100 : 0}
                      sx={{ bgcolor: '#333' }}
                      aria-label={`${bot.name} win rate`}
                    />
                    <Typography variant="caption" color="textSecondary">
                      {bot.total_trades > 0 ? ((bot.successful_trades / bot.total_trades) * 100).toFixed(1) : 0}%
                    </Typography>
                  </Box>

                  <div role="status" aria-live="polite" aria-atomic="true">
                    {bot.running ? (
                      <Box display="flex" gap={1}>
                        <Button
                          fullWidth
                          variant="contained"
                          startIcon={<Pause aria-hidden="true" />}
                          sx={{ bgcolor: '#ffaa00', color: '#000' }}
                          onClick={() => handleControlBot(bot.name, 'pause')}
                          disabled={bot.paused}
                          aria-label={`Pause bot ${bot.name}`}
                        >
                          Pause
                        </Button>
                        <IconButton
                          color="error"
                          onClick={() => handleControlBot(bot.name, 'stop')}
                          aria-label={`Stop bot ${bot.name}`}
                        >
                          <Stop aria-hidden="true" />
                        </IconButton>
                      </Box>
                    ) : (
                      <Button
                        fullWidth
                        variant="contained"
                        startIcon={<PlayArrow aria-hidden="true" />}
                        sx={{ bgcolor: '#00ff88', color: '#000' }}
                        onClick={() => handleControlBot(bot.name, 'start')}
                        aria-label={`Start bot ${bot.name}`}
                      >
                        Start
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>

      {/* Create Bot Dialog */}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        maxWidth="sm"
        fullWidth
        aria-labelledby="create-bot-dialog-title"
        aria-describedby="create-bot-dialog-desc"
      >
        <DialogTitle id="create-bot-dialog-title" sx={{ color: '#00ff88' }}>Create New Bot</DialogTitle>
        <DialogContent>
          <Typography id="create-bot-dialog-desc" variant="body2" color="textSecondary" sx={{ mb: 1 }}>
            Configure your new automated trading bot below.
          </Typography>
          <TextField
            fullWidth
            id="bot-name"
            label="Bot Name"
            margin="normal"
            value={newBot.name}
            onChange={(e) => setNewBot({ ...newBot, name: e.target.value })}
            sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
            inputRef={firstInputRef}
            inputProps={{ 'aria-required': 'true' }}
          />
          <FormControl fullWidth margin="normal">
            <InputLabel id="bot-exchange-label">Exchange</InputLabel>
            <Select
              labelId="bot-exchange-label"
              id="bot-exchange"
              value={newBot.exchange}
              label="Exchange"
              onChange={(e) => setNewBot({ ...newBot, exchange: e.target.value })}
              sx={{ bgcolor: '#0a0a0a' }}
            >
              <MenuItem value="binance">Binance</MenuItem>
              <MenuItem value="kraken">Kraken</MenuItem>
              <MenuItem value="coinbase">Coinbase</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel id="bot-symbol-label">Symbol</InputLabel>
            <Select
              labelId="bot-symbol-label"
              id="bot-symbol"
              value={newBot.symbol}
              label="Symbol"
              onChange={(e) => setNewBot({ ...newBot, symbol: e.target.value })}
              sx={{ bgcolor: '#0a0a0a' }}
            >
              <MenuItem value="BTC/USDT">BTC/USDT</MenuItem>
              <MenuItem value="ETH/USDT">ETH/USDT</MenuItem>
              <MenuItem value="SOL/USDT">SOL/USDT</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel id="bot-strategy-label">Strategy</InputLabel>
            <Select
              labelId="bot-strategy-label"
              id="bot-strategy"
              value={newBot.strategy}
              label="Strategy"
              onChange={(e) => setNewBot({ ...newBot, strategy: e.target.value })}
              sx={{ bgcolor: '#0a0a0a' }}
            >
              <MenuItem value="ma_crossover">MA Crossover</MenuItem>
              <MenuItem value="rsi_reversal">RSI Reversal</MenuItem>
              <MenuItem value="macd_momentum">MACD Momentum</MenuItem>
              <MenuItem value="bollinger_breakout">Bollinger Breakout</MenuItem>
              <MenuItem value="grid_trading">Grid Trading</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button 
            variant="contained" 
            onClick={handleCreateBot}
            sx={{ bgcolor: '#00ff88', color: '#000' }}
          >
            Create Bot
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Bots;