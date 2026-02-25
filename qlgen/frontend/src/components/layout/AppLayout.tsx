import React, { useState } from 'react';
import { Box, List, ListItemButton, ListItemIcon, ListItemText, Typography, Avatar } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useNavigate, useLocation } from 'react-router-dom';

const DRAWER_OPEN = 248;
const DRAWER_CLOSED = 64;

const navItems = [
  { key: '/dashboard', icon: <DashboardIcon sx={{ fontSize: 18 }} />, label: 'Dashboard' },
  { key: '/icp', icon: <BookmarkIcon sx={{ fontSize: 18 }} />, label: 'Saved ICPs' },
];

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const drawerWidth = collapsed ? DRAWER_CLOSED : DRAWER_OPEN;

  const activeKey =
    navItems.find((item) => location.pathname === item.key || location.pathname.startsWith(item.key + '/'))?.key ||
    '/dashboard';

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#FAFAFA' }}>
      {/* Sidebar */}
      <Box
        sx={{
          width: drawerWidth,
          position: 'fixed',
          top: 0, left: 0, bottom: 0,
          bgcolor: '#fff',
          borderRight: '1px solid #EBEBEB',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 100,
          transition: 'width .2s ease',
          overflow: 'hidden',
        }}
      >
        {/* Logo */}
        <Box
          sx={{
            px: '20px',
            pt: '20px',
            pb: 0,
            mb: 3.5,
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
        >
          <Box
            sx={{
              width: 34, height: 34,
              background: 'linear-gradient(135deg, #5C2D8F, #7B4DB5)',
              borderRadius: '9px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 700, color: '#fff', flexShrink: 0,
              boxShadow: '0 2px 8px rgba(92,45,143,.3)',
            }}
          >
            ql
          </Box>
          {!collapsed && (
            <Typography sx={{ fontSize: 18, fontWeight: 700, color: '#242424', letterSpacing: '-0.3px', whiteSpace: 'nowrap' }}>
              qlGen
            </Typography>
          )}
        </Box>

        {/* Nav items */}
        <List disablePadding sx={{ px: 1 }}>
          {navItems.map((item) => {
            const isActive = activeKey === item.key;
            return (
              <ListItemButton
                key={item.key}
                onClick={() => navigate(item.key)}
                sx={{
                  borderRadius: '8px',
                  mb: '1px',
                  px: 1.5,
                  py: '9px',
                  minHeight: 'unset',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  bgcolor: isActive ? '#F4EFFE' : 'transparent',
                  color: isActive ? '#5C2D8F' : '#858585',
                  '&:hover': {
                    bgcolor: isActive ? '#F4EFFE' : '#F5F5F5',
                    color: isActive ? '#5C2D8F' : '#242424',
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: collapsed ? 0 : 30,
                    color: 'inherit',
                    justifyContent: 'center',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                {!collapsed && (
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{ fontSize: 14, fontWeight: 500, letterSpacing: '-0.1px', color: 'inherit' }}
                  />
                )}
              </ListItemButton>
            );
          })}
        </List>

        <Box sx={{ flexGrow: 1 }} />

        {/* User area */}
        <Box
          sx={{
            p: '14px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            borderTop: '1px solid #EBEBEB',
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
        >
          <Avatar
            sx={{
              width: 34, height: 34,
              background: 'linear-gradient(135deg, #F4693B, #f7934b)',
              fontSize: 13, fontWeight: 600, flexShrink: 0,
            }}
          >
            AK
          </Avatar>
          {!collapsed && (
            <Box>
              <Typography sx={{ fontSize: 13, fontWeight: 500, color: '#3D3D3D', lineHeight: 1.3 }}>
                Aarav K.
              </Typography>
              <Typography sx={{ fontSize: 11, color: '#ADADAD', mt: '1px' }}>
                Sales Lead
              </Typography>
            </Box>
          )}
        </Box>

        {/* Collapse toggle */}
        <Box
          onClick={() => setCollapsed((c) => !c)}
          sx={{
            px: '20px',
            py: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            borderTop: '1px solid #EBEBEB',
            cursor: 'pointer',
            color: '#ADADAD',
            justifyContent: collapsed ? 'center' : 'flex-start',
            '&:hover': { color: '#3D3D3D' },
            transition: 'color .15s',
          }}
        >
          {collapsed ? (
            <ChevronRightIcon sx={{ fontSize: 16 }} />
          ) : (
            <>
              <ChevronLeftIcon sx={{ fontSize: 16 }} />
              <Typography sx={{ fontSize: 12, color: 'inherit' }}>Collapse</Typography>
            </>
          )}
        </Box>
      </Box>

      {/* Main content */}
      <Box
        sx={{
          ml: `${drawerWidth}px`,
          transition: 'margin-left .2s ease',
          flexGrow: 1,
          minHeight: '100vh',
        }}
      >
        <Box sx={{ p: '28px 32px', maxWidth: 1400, mx: 'auto' }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
};

export default AppLayout;
