import React from 'react';
import { Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SecurityIcon from '@mui/icons-material/Security';
import SettingsIcon from '@mui/icons-material/Settings';

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
    { text: 'Trading', icon: <ShowChartIcon />, path: '/trading' },
    { text: 'Bots', icon: <SmartToyIcon />, path: '/bots' },
    { text: 'Security', icon: <SecurityIcon />, path: '/security' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ];

  return (
    <Drawer
      variant="permanent"
      aria-label="Main navigation"
      sx={{
        width: 240,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: 240,
          boxSizing: 'border-box',
          bgcolor: '#0a0a0a',
          borderRight: '1px solid #333',
        },
      }}
    >
      <List>
        <ListItem sx={{ mb: 2 }}>
          <Typography variant="h6" component="span" sx={{ color: '#00ff88', fontWeight: 'bold' }}>
            RIMURU
          </Typography>
        </ListItem>
        
        {menuItems.map((item) => (
          <ListItemButton
            key={item.text}
            selected={location.pathname === item.path}
            aria-current={location.pathname === item.path ? 'page' : undefined}
            onClick={() => navigate(item.path)}
            sx={{
              mb: 1,
              borderRadius: 1,
              mx: 1,
              bgcolor: location.pathname === item.path ? '#1a1a1a' : 'transparent',
              '&:hover': {
                bgcolor: '#1a1a1a',
              },
            }}
          >
            <ListItemIcon sx={{ color: location.pathname === item.path ? '#00ff88' : '#666' }} aria-hidden="true">
              {item.icon}
            </ListItemIcon>
            <ListItemText
              primary={item.text}
              sx={{
                color: location.pathname === item.path ? '#00ff88' : '#fff',
              }}
            />
          </ListItemButton>
        ))}
      </List>
      
      <div style={{ position: 'absolute', bottom: 16, left: 16, right: 16 }}>
        <Typography variant="caption" color="textSecondary">
          Version 1.0.0
        </Typography>
      </div>
    </Drawer>
  );
};

export default Navigation;