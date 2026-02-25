import { AppBar, Toolbar, Typography, Box } from '@mui/material';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import { DRAWER_WIDTH } from './Sidebar';

export default function Header() {
  return (
    <AppBar
      position="fixed"
      elevation={1}
      sx={{ width: `calc(100% - ${DRAWER_WIDTH}px)`, ml: `${DRAWER_WIDTH}px` }}
    >
      <Toolbar>
        <AutoGraphIcon sx={{ mr: 1.5 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          qlGen
        </Typography>
        <Box>
          <Typography variant="caption" color="inherit" sx={{ opacity: 0.8 }}>
            Qualified Lead Generator
          </Typography>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
