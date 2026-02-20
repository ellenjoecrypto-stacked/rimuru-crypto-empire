import React, { useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Alert,
  Divider,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Snackbar,
  Avatar,
  IconButton,
} from '@mui/material';
import {
  AccountCircle,
  Notifications,
  TuneOutlined,
  Save,
  Edit,
} from '@mui/icons-material';

const AccountSettings: React.FC = () => {
  const [saved, setSaved] = useState(false);

  // Profile state
  const [profile, setProfile] = useState({
    displayName: 'Rimuru Trader',
    email: 'trader@rimuru.local',
    timezone: 'UTC',
  });

  // Notification preferences
  const [notifications, setNotifications] = useState({
    tradeExecuted: true,
    botStatusChange: true,
    priceAlerts: false,
    dailySummary: true,
    emailAlerts: false,
  });

  // Trading preferences
  const [tradingPrefs, setTradingPrefs] = useState({
    defaultCurrency: 'USD',
    riskLevel: 'medium',
    autoStopLoss: true,
    confirmTrades: true,
    maxDailyTrades: '20',
  });

  const handleSave = () => {
    // In a real app this would call the API
    setSaved(true);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ color: '#00ff88', fontWeight: 'bold' }}>
        Account Settings
      </Typography>

      <Grid container spacing={3}>
        {/* Profile Section */}
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '100%' }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <AccountCircle sx={{ color: '#00ff88', fontSize: 32, mr: 2 }} />
                <Typography variant="h6" sx={{ color: '#00ff88' }}>
                  Profile
                </Typography>
              </Box>

              <Box display="flex" alignItems="center" mb={3}>
                <Avatar
                  sx={{
                    width: 64,
                    height: 64,
                    bgcolor: '#00ff88',
                    color: '#000',
                    fontSize: 28,
                    fontWeight: 'bold',
                    mr: 2,
                  }}
                >
                  {profile.displayName.charAt(0)}
                </Avatar>
                <IconButton size="small" sx={{ color: '#666' }}>
                  <Edit fontSize="small" />
                </IconButton>
              </Box>

              <TextField
                fullWidth
                label="Display Name"
                margin="normal"
                value={profile.displayName}
                onChange={(e) => setProfile({ ...profile, displayName: e.target.value })}
                sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
              />
              <TextField
                fullWidth
                label="Email"
                margin="normal"
                type="email"
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
              />
              <FormControl fullWidth margin="normal">
                <InputLabel>Timezone</InputLabel>
                <Select
                  value={profile.timezone}
                  label="Timezone"
                  onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                  sx={{ bgcolor: '#0a0a0a' }}
                >
                  <MenuItem value="UTC">UTC</MenuItem>
                  <MenuItem value="America/New_York">Eastern (US)</MenuItem>
                  <MenuItem value="America/Chicago">Central (US)</MenuItem>
                  <MenuItem value="America/Los_Angeles">Pacific (US)</MenuItem>
                  <MenuItem value="Europe/London">London</MenuItem>
                  <MenuItem value="Asia/Tokyo">Tokyo</MenuItem>
                </Select>
              </FormControl>
            </CardContent>
          </Card>
        </Grid>

        {/* Notifications Section */}
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '100%' }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <Notifications sx={{ color: '#00ff88', fontSize: 32, mr: 2 }} />
                <Typography variant="h6" sx={{ color: '#00ff88' }}>
                  Notifications
                </Typography>
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.tradeExecuted}
                    onChange={(e) =>
                      setNotifications({ ...notifications, tradeExecuted: e.target.checked })
                    }
                    sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                  />
                }
                label="Trade Executed"
                sx={{ display: 'flex', mb: 1 }}
              />
              <Divider sx={{ bgcolor: '#333', my: 1 }} />
              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.botStatusChange}
                    onChange={(e) =>
                      setNotifications({ ...notifications, botStatusChange: e.target.checked })
                    }
                    sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                  />
                }
                label="Bot Status Change"
                sx={{ display: 'flex', mb: 1 }}
              />
              <Divider sx={{ bgcolor: '#333', my: 1 }} />
              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.priceAlerts}
                    onChange={(e) =>
                      setNotifications({ ...notifications, priceAlerts: e.target.checked })
                    }
                    sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                  />
                }
                label="Price Alerts"
                sx={{ display: 'flex', mb: 1 }}
              />
              <Divider sx={{ bgcolor: '#333', my: 1 }} />
              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.dailySummary}
                    onChange={(e) =>
                      setNotifications({ ...notifications, dailySummary: e.target.checked })
                    }
                    sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                  />
                }
                label="Daily Summary"
                sx={{ display: 'flex', mb: 1 }}
              />
              <Divider sx={{ bgcolor: '#333', my: 1 }} />
              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.emailAlerts}
                    onChange={(e) =>
                      setNotifications({ ...notifications, emailAlerts: e.target.checked })
                    }
                    sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                  />
                }
                label="Email Alerts"
                sx={{ display: 'flex', mb: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Trading Preferences Section */}
        <Grid item xs={12}>
          <Card sx={{ bgcolor: '#1a1a1a' }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <TuneOutlined sx={{ color: '#00ff88', fontSize: 32, mr: 2 }} />
                <Typography variant="h6" sx={{ color: '#00ff88' }}>
                  Trading Preferences
                </Typography>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <FormControl fullWidth>
                    <InputLabel>Default Currency</InputLabel>
                    <Select
                      value={tradingPrefs.defaultCurrency}
                      label="Default Currency"
                      onChange={(e) =>
                        setTradingPrefs({ ...tradingPrefs, defaultCurrency: e.target.value })
                      }
                      sx={{ bgcolor: '#0a0a0a' }}
                    >
                      <MenuItem value="USD">USD</MenuItem>
                      <MenuItem value="EUR">EUR</MenuItem>
                      <MenuItem value="BTC">BTC</MenuItem>
                      <MenuItem value="USDT">USDT</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <FormControl fullWidth>
                    <InputLabel>Risk Level</InputLabel>
                    <Select
                      value={tradingPrefs.riskLevel}
                      label="Risk Level"
                      onChange={(e) =>
                        setTradingPrefs({ ...tradingPrefs, riskLevel: e.target.value })
                      }
                      sx={{ bgcolor: '#0a0a0a' }}
                    >
                      <MenuItem value="low">Low</MenuItem>
                      <MenuItem value="medium">Medium</MenuItem>
                      <MenuItem value="high">High</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <TextField
                    fullWidth
                    label="Max Daily Trades"
                    type="number"
                    value={tradingPrefs.maxDailyTrades}
                    onChange={(e) =>
                      setTradingPrefs({ ...tradingPrefs, maxDailyTrades: e.target.value })
                    }
                    inputProps={{ min: 1, max: 1000 }}
                    sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box display="flex" flexDirection="column" gap={1} pt={1}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={tradingPrefs.autoStopLoss}
                          onChange={(e) =>
                            setTradingPrefs({ ...tradingPrefs, autoStopLoss: e.target.checked })
                          }
                          sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                        />
                      }
                      label="Auto Stop-Loss"
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          checked={tradingPrefs.confirmTrades}
                          onChange={(e) =>
                            setTradingPrefs({ ...tradingPrefs, confirmTrades: e.target.checked })
                          }
                          sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#00ff88' } }}
                        />
                      }
                      label="Confirm Trades"
                    />
                  </Box>
                </Grid>
              </Grid>

              {tradingPrefs.riskLevel === 'high' && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  <strong>High Risk Mode:</strong> Bots may take larger positions. Ensure you
                  understand the risks before proceeding.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Save Button */}
        <Grid item xs={12}>
          <Box display="flex" justifyContent="flex-end">
            <Button
              variant="contained"
              size="large"
              startIcon={<Save />}
              onClick={handleSave}
              sx={{ bgcolor: '#00ff88', color: '#000', fontWeight: 'bold' }}
            >
              Save Settings
            </Button>
          </Box>
        </Grid>
      </Grid>

      <Snackbar
        open={saved}
        autoHideDuration={3000}
        onClose={() => setSaved(false)}
        message="Settings saved successfully"
      />
    </Box>
  );
};

export default AccountSettings;
