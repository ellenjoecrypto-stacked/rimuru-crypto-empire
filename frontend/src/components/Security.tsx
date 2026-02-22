import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon
} from '@mui/material';
import {
  Security as SecurityIcon,
  VpnKey,
  Delete,
  Add,
  Lock,
  Warning,
  CheckCircle,
  Error as ErrorIcon
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

interface AuditLog {
  timestamp: string;
  action: string;
  exchange: string;
  details: string;
}

interface Exchange {
  name: string;
  type: string;
  sandbox: boolean;
  active: boolean;
}

const Security: React.FC = () => {
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [open, setOpen] = useState(false);
  const [newExchange, setNewExchange] = useState({
    name: '',
    exchange_type: 'binance',
    api_key: '',
    secret_key: '',
    sandbox: true
  });
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open && firstInputRef.current) {
      firstInputRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [exchangesRes, auditRes] = await Promise.all([
        axios.get(`${API_URL}/exchanges`),
        axios.get(`${API_URL}/credentials/audit-log`)
      ]);
      setExchanges(exchangesRes.data.exchanges);
      setAuditLogs(auditRes.data.audit_log || []);
    } catch (error) {
      console.error('Error fetching security data:', error);
    }
  };

  const handleAddExchange = async () => {
    try {
      await axios.post(`${API_URL}/exchanges/add`, newExchange);
      setOpen(false);
      await fetchData();
      alert('Exchange added successfully!');
    } catch (error) {
      console.error('Error adding exchange:', error);
      alert('Failed to add exchange');
    }
  };

  const handleRemoveExchange = async (name: string) => {
    if (window.confirm(`Are you sure you want to remove ${name}?`)) {
      try {
        await axios.delete(`${API_URL}/exchanges/${name}`);
        await fetchData();
      } catch (error) {
        console.error('Error removing exchange:', error);
        alert('Failed to remove exchange');
      }
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom sx={{ color: '#00ff88', fontWeight: 'bold' }}>
        Security Center
      </Typography>

      <Alert severity="warning" sx={{ mb: 3 }}>
        <strong>Security Warning:</strong> Never enable withdrawal permissions on your API keys. 
        Always use IP whitelisting on your exchange accounts.
      </Alert>

      <Grid container spacing={3}>
        {/* Security Status */}
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: '#1a1a1a', height: '100%' }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <SecurityIcon sx={{ color: '#00ff88', fontSize: 32, mr: 2 }} aria-hidden="true" />
                <Typography variant="h6" component="h2" sx={{ color: '#00ff88' }}>
                  Security Status
                </Typography>
              </Box>
              
              <List>
                <ListItem>
                  <ListItemIcon><CheckCircle sx={{ color: '#00ff88' }} aria-hidden="true" /></ListItemIcon>
                  <ListItemText primary="Credential Vault Active" secondary="AES-256-GCM encryption" />
                </ListItem>
                <ListItem>
                  <ListItemIcon><CheckCircle sx={{ color: '#00ff88' }} aria-hidden="true" /></ListItemIcon>
                  <ListItemText primary="Audit Logging Enabled" secondary={`${auditLogs.length} entries`} />
                </ListItem>
                <ListItem>
                  <ListItemIcon><CheckCircle sx={{ color: '#00ff88' }} aria-hidden="true" /></ListItemIcon>
                  <ListItemText primary="2FA Supported" secondary="Use exchange 2FA" />
                </ListItem>
                <ListItem>
                  <ListItemIcon><ErrorIcon sx={{ color: '#ffaa00' }} aria-hidden="true" /></ListItemIcon>
                  <ListItemText primary="IP Whitelisting" secondary="Configure on exchange" />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Connected Exchanges */}
        <Grid item xs={12} md={8}>
          <Card sx={{ bgcolor: '#1a1a1a' }}>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Box display="flex" alignItems="center">
                  <VpnKey sx={{ color: '#00ff88', mr: 1 }} aria-hidden="true" />
                  <Typography variant="h6" component="h2" sx={{ color: '#00ff88' }}>
                    Connected Exchanges
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  sx={{ bgcolor: '#00ff88', color: '#000' }}
                  onClick={() => setOpen(true)}
                >
                  Add Exchange
                </Button>
              </Box>

              {exchanges.length === 0 ? (
                <Box textAlign="center" py={4}>
                  <Lock sx={{ fontSize: 48, color: '#666', mb: 2 }} aria-hidden="true" />
                  <Typography variant="body1" color="textSecondary">
                    No exchanges connected
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Add your exchange API keys to start trading
                  </Typography>
                </Box>
              ) : (
                <TableContainer>
                  <Table aria-label="Connected exchanges">
                    <caption className="visually-hidden">List of connected exchange accounts and their status</caption>
                    <TableHead>
                      <TableRow>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Name</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Type</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Mode</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Status</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {exchanges.map((exchange) => (
                        <TableRow key={exchange.name}>
                          <TableCell component="th" scope="row" sx={{ color: '#fff' }}>{exchange.name}</TableCell>
                          <TableCell sx={{ color: '#fff' }}>{exchange.type.toUpperCase()}</TableCell>
                          <TableCell>
                            <Chip 
                              label={exchange.sandbox ? 'Sandbox' : 'Live'}
                              size="small"
                              sx={{ 
                                bgcolor: exchange.sandbox ? '#ffaa00' : '#ff4444',
                                color: '#000'
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={exchange.active ? 'Connected' : 'Disconnected'}
                              size="small"
                              sx={{ 
                                bgcolor: exchange.active ? '#00ff88' : '#666',
                                color: '#000'
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <IconButton 
                              color="error" 
                              onClick={() => handleRemoveExchange(exchange.name)}
                              aria-label={`Remove exchange ${exchange.name}`}
                            >
                              <Delete aria-hidden="true" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Security Best Practices */}
        <Grid item xs={12}>
          <Card sx={{ bgcolor: '#1a1a1a' }}>
            <CardContent>
              <Typography variant="h6" component="h2" gutterBottom sx={{ color: '#00ff88' }}>
                <Warning sx={{ verticalAlign: 'middle', mr: 1 }} aria-hidden="true" />
                Security Best Practices
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Alert severity="error" sx={{ bgcolor: '#2a1a1a' }}>
                    <strong>NEVER</strong> enable withdrawal permissions on API keys
                  </Alert>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Alert severity="error" sx={{ bgcolor: '#2a1a1a' }}>
                    <strong>NEVER</strong> share your API keys with anyone
                  </Alert>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Alert severity="success" sx={{ bgcolor: '#1a2a1a' }}>
                    <strong>ALWAYS</strong> use IP whitelisting on exchanges
                  </Alert>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Alert severity="success" sx={{ bgcolor: '#1a2a1a' }}>
                    <strong>ALWAYS</strong> enable 2FA on all accounts
                  </Alert>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Alert severity="success" sx={{ bgcolor: '#1a2a1a' }}>
                    <strong>ALWAYS</strong> rotate API keys regularly
                  </Alert>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Alert severity="success" sx={{ bgcolor: '#1a2a1a' }}>
                    <strong>ALWAYS</strong> monitor audit logs regularly
                  </Alert>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Audit Log */}
        <Grid item xs={12}>
          <Card sx={{ bgcolor: '#1a1a1a' }}>
            <CardContent>
              <Typography variant="h6" component="h2" gutterBottom sx={{ color: '#00ff88' }}>
                Recent Activity (Audit Log)
              </Typography>
              
              {auditLogs.length === 0 ? (
                <Typography variant="body2" color="textSecondary">
                  No recent activity
                </Typography>
              ) : (
                <TableContainer>
                  <Table aria-label="Audit log">
                    <caption className="visually-hidden">Recent audit log entries showing actions performed on exchange accounts</caption>
                    <TableHead>
                      <TableRow>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Timestamp</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Action</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Exchange</TableCell>
                        <TableCell component="th" scope="col" sx={{ color: '#666' }}>Details</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {auditLogs.slice(0, 10).map((log, index) => (
                        <TableRow key={index}>
                          <TableCell component="th" scope="row" sx={{ color: '#fff', fontSize: '0.875rem' }}>
                            {new Date(log.timestamp).toLocaleString()}
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={log.action}
                              size="small"
                              sx={{ 
                                bgcolor: log.action === 'STORE' ? '#00ff88' : 
                                       log.action === 'RETRIEVE' ? '#ffaa00' : '#ff4444',
                                color: '#000'
                              }}
                            />
                          </TableCell>
                          <TableCell sx={{ color: '#fff' }}>{log.exchange}</TableCell>
                          <TableCell sx={{ color: '#fff' }}>{log.details}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Add Exchange Dialog */}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        maxWidth="sm"
        fullWidth
        aria-labelledby="add-exchange-dialog-title"
        aria-describedby="add-exchange-dialog-desc"
      >
        <DialogTitle id="add-exchange-dialog-title" sx={{ color: '#00ff88' }}>Add Exchange</DialogTitle>
        <DialogContent>
          <Typography id="add-exchange-dialog-desc" variant="body2" color="textSecondary" sx={{ mb: 1 }}>
            Enter your exchange API credentials. Keys are encrypted before storage.
          </Typography>
          <TextField
            fullWidth
            id="exchange-name"
            label="Exchange Name"
            margin="normal"
            value={newExchange.name}
            onChange={(e) => setNewExchange({ ...newExchange, name: e.target.value })}
            sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
            inputRef={firstInputRef}
            inputProps={{ 'aria-required': 'true' }}
          />
          <Alert severity="info" sx={{ mt: 2 }}>
            API keys are encrypted with AES-256-GCM before storage.
          </Alert>
          <TextField
            fullWidth
            id="exchange-api-key"
            label="API Key"
            margin="normal"
            type="password"
            value={newExchange.api_key}
            onChange={(e) => setNewExchange({ ...newExchange, api_key: e.target.value })}
            sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
            inputProps={{ autoComplete: 'off', 'aria-required': 'true' }}
          />
          <TextField
            fullWidth
            id="exchange-secret-key"
            label="Secret Key"
            margin="normal"
            type="password"
            value={newExchange.secret_key}
            onChange={(e) => setNewExchange({ ...newExchange, secret_key: e.target.value })}
            sx={{ '& .MuiInputBase-root': { bgcolor: '#0a0a0a' } }}
            inputProps={{ autoComplete: 'off', 'aria-required': 'true' }}
          />
          <Alert severity="warning" sx={{ mt: 2 }}>
            Make sure this API key does NOT have withdrawal permissions!
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button 
            variant="contained" 
            onClick={handleAddExchange}
            sx={{ bgcolor: '#00ff88', color: '#000' }}
          >
            Add Exchange
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Security;