const { app, BrowserWindow, ipcMain, Menu, Tray } = require('electron')
const fs = require('fs')
const axios = require('axios')
const path = require('path')
const { exec } = require('child_process')
require('dotenv').config()

// API endpoints configuration
const AUTH_API_URL = `http://${process.env.AUTH_API_HOST || 'localhost'}:${process.env.AUTH_API_PORT || '8501'}`
let CONTAINER_API_URL = null;

axios.defaults.debug = false

let mainWindow
let tray = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 640,
    height: 480,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    }
  })

  mainWindow.loadFile('index.html')

  // Remove menu bar while keeping title bar
  Menu.setApplicationMenu(null)
  
  // Open the DevTools in development mode
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools()
  }

  // Create system tray after app is ready
  app.whenReady().then(() => {
    try {
      const iconPath = path.join(__dirname, 'assets', 'icon.png')
      if (!fs.existsSync(iconPath)) {
        throw new Error(`Icon file not found at ${iconPath}`)
      }

      tray = new Tray(iconPath)
      const contextMenu = Menu.buildFromTemplate([
        {
          label: 'Container Actions',
          submenu: [
            {
              label: 'Create',
              icon: path.join(__dirname, 'assets', 'create.png'),
              click: () => mainWindow.webContents.send('container-action', 'create')
            },
            {
              label: 'Start',
              icon: path.join(__dirname, 'assets', 'start.png'),
              click: () => mainWindow.webContents.send('container-action', 'start')
            },
            {
              label: 'Stop',
              icon: path.join(__dirname, 'assets', 'stop.png'),
              click: () => mainWindow.webContents.send('container-action', 'stop')
            },
            {
              label: 'Restart',
              icon: path.join(__dirname, 'assets', 'restart.png'),
              click: () => mainWindow.webContents.send('container-action', 'restart')
            },
            {
              label: 'Remove',
              icon: path.join(__dirname, 'assets', 'remove.png'),
              click: () => mainWindow.webContents.send('container-action', 'remove')
            }
          ]
        },
        {
          label: 'Services',
          submenu: [
            {
              label: 'VS Code',
              icon: path.join(__dirname, 'assets', 'vscode.png'),
              click: () => mainWindow.webContents.send('service-action', 'vscode')
            },
            {
              label: 'SSH',
              icon: path.join(__dirname, 'assets', 'ssh.png'),
              click: () => mainWindow.webContents.send('service-action', 'ssh')
            },
            {
              label: 'RDP',
              icon: path.join(__dirname, 'assets', 'rdp.png'),
              click: () => mainWindow.webContents.send('service-action', 'rdp')
            },
            {
              label: 'FM UI',
              icon: path.join(__dirname, 'assets', 'fm.png'),
              click: () => mainWindow.webContents.send('service-action', 'fm')
            }
          ]
        },
        { type: 'separator' },
        {
          label: 'Quit',
          click: () => app.quit()
        }
      ])
      tray.setToolTip('CXL Remote Development')
      tray.setContextMenu(contextMenu)
    } catch (error) {
      console.error('Failed to create system tray:', error)
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Auth-related IPC Handlers
const authAxios = axios.create({
  baseURL: AUTH_API_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
  retry: 2,
  retryDelay: 1000
});

// Keep track of pending requests
const pendingRequests = new Map();

// Add request interceptor
authAxios.interceptors.request.use(config => {
  const requestId = Math.random().toString(36).substring(7);
  config.requestId = requestId;
  
  // Cancel previous pending request for the same endpoint
  const previousRequest = pendingRequests.get(config.url);
  if (previousRequest) {
    previousRequest.cancel('Request superseded by newer request');
  }
  
  // Create new cancel token
  const source = axios.CancelToken.source();
  config.cancelToken = source.token;
  pendingRequests.set(config.url, source);
  
  return config;
});

// Add response interceptor to clean up pending requests
authAxios.interceptors.response.use(
  response => {
    pendingRequests.delete(response.config.url);
    return response;
  },
  error => {
    if (error.config) {
      pendingRequests.delete(error.config.url);
    }
    throw error;
  }
);

const handleAuthError = (error, operation) => {
  if (axios.isCancel(error)) {
    return { success: false, error: 'Request cancelled' };
  }
  
  const errorMessage = error.response?.data?.error || `${operation} failed`;
  const statusCode = error.response?.status;
  
  console.error(`${operation} failed:`, {
    message: errorMessage,
    statusCode,
    timestamp: new Date().toISOString()
  });
  
  return { 
    success: false, 
    error: errorMessage,
    statusCode
  };
};

ipcMain.handle('login', async (event, { username, password }) => {
  try {
    const response = await authAxios.post('/api/login', { username, password });
    return response.data;
  } catch (error) {
    return handleAuthError(error, 'Login');
  }
});

ipcMain.handle('validate-session', async (event, { userId, sessionToken }) => {
  try {
    const response = await authAxios.post('/api/validate_session', {
      user_id: userId,
      session_token: sessionToken
    });
    return response.data;
  } catch (error) {
    return handleAuthError(error, 'Session validation');
  }
});

ipcMain.handle('logout', async (event, { userId }) => {
  try {
    const response = await authAxios.post('/api/logout', { user_id: userId });
    return response.data;
  } catch (error) {
    return handleAuthError(error, 'Logout');
  }
});

ipcMain.handle('get-user-info', async (event, { userId }) => {
  try {
    const response = await authAxios.get(`/api/users/${userId}`);
    console.error(response.data)
    return response.data;
  } catch (error) {
    return handleAuthError(error, 'Get user info');
  }
});

// Container-related IPC Handlers
let containerAxios = null;

ipcMain.handle('set-container-api', async (event, { ip, port }) => {
  // Create new axios instance with updated base URL
  console.error(ip, port)
  containerAxios = axios.create({
    baseURL: `http://${ip}:${port}`,
    timeout: 15000,
    headers: { 'Content-Type': 'application/json' },
    retry: 2,
    retryDelay: 1000
  });

  // Set up interceptors
  containerAxios.interceptors.response.use(
    response => {
      if (response.config.url.includes('/stats') && !response.data.running) {
        const containerId = response.config.url.split('/')[3];
        const polling = statsPolling.get(containerId);
        if (polling) {
          clearInterval(polling);
          statsPolling.delete(containerId);
        }
      }
      return response;
    },
    error => { throw error; }
  );

  return { success: true };
});

// Track container stats polling
const statsPolling = new Map();

const handleContainerError = (error, operation) => {
  if (axios.isCancel(error)) {
    return { success: false, error: 'Request cancelled' };
  }

  const errorMessage = error.response?.data?.error || `Failed to ${operation}`;
  const statusCode = error.response?.status;

  console.error(`Container operation failed:`, {
    operation,
    message: errorMessage,
    statusCode,
    timestamp: new Date().toISOString()
  });

  return {
    success: false,
    error: errorMessage,
    statusCode
  };
};

ipcMain.handle('get-container-info', async (event, containerId) => {
  if (!containerAxios) {
    return { success: false, error: 'Container API not set' };
  }

  try {
    const response = await containerAxios.get(`/api/containers/${containerId}`);
    console.error(response.data)
    return response.data;
  } catch (error) {
    return handleContainerError(error, 'fetch container info');
  }
});

ipcMain.handle('get-container-stats', async (event, containerId) => {
  if (!containerAxios) {
    return { success: false, error: 'Container API not set' };
  }

  try {
    // Cancel any existing polling for this container
    if (statsPolling.has(containerId)) {
      clearInterval(statsPolling.get(containerId));
    }

    const fetchStats = async () => {
      try {
        const response = await containerAxios.get(`/api/containers/${containerId}/stats`);
        event.sender.send('container-stats-update', { containerId, stats: response.data });
        return response.data;
      } catch (error) {
        const errorResult = handleContainerError(error, 'fetch container stats');
        event.sender.send('container-stats-error', { containerId, error: errorResult });
        return errorResult;
      }
    };

    // Initial fetch
    const initialStats = await fetchStats();
    
    // Set up polling if container is running
    if (initialStats.running) {
      const pollInterval = setInterval(fetchStats, 5000); // Poll every 5 seconds
      statsPolling.set(containerId, pollInterval);
    }

    return initialStats;
  } catch (error) {
    return handleContainerError(error, 'fetch container stats');
  }
});

ipcMain.handle('container-action', async (event, { action, containerId }) => {
  if (!containerAxios) {
    return { success: false, error: 'Container API not set' };
  }

  console.error(action, containerId)
  try {
    const response = await containerAxios.post(`/api/containers/${containerId}/${action}`);
    
    // If stopping container, clear stats polling
    if (action === 'stop' && statsPolling.has(containerId)) {
      clearInterval(statsPolling.get(containerId));
      statsPolling.delete(containerId);
    }
    console.error(response.data)
    return response.data;
  } catch (error) {
    return handleContainerError(error, `perform ${action}`);
  }
});

ipcMain.handle('container-create', async (event, username, sessionToken) => {
  if (!containerAxios) {
    return { success: false, error: 'Container API not set' };
  }

  console.error(username, sessionToken)
  try {
    const response = await containerAxios.post('/api/containers', {
      user: username,
      session_token: sessionToken
    });
    return response.data;
  } catch (error) {
    return handleContainerError(error, 'create container');
  }
});

ipcMain.handle('generate-user-hash', async (event, username) => {
  const crypto = require('crypto')
  const hash = crypto.createHash('sha256').update(username).digest('hex')
  return hash.substring(0, 16)
})

// Add port fetching handler
ipcMain.handle('get-container-ports', async (event, containerId) => {
  if (!containerAxios) {
    return { success: false, error: 'Container API not set' };
  }
  try {
    const response = await containerAxios.get(`/api/containers/${containerId}/ports`);
    return response.data;
  } catch (error) {
    return handleContainerError(error, 'fetching ports');
  }
});

// Handle remote-viewer launch
ipcMain.handle('launch-remote-viewer', async (event, { host, port }) => {
  return new Promise((resolve, reject) => {
    const command = `remote-viewer spice://${host}:${port}`;
    exec(command, (error, stdout, stderr) => {
      if (error) {
        console.error('Error launching remote-viewer:', error);
        reject(error);
        return;
      }
      resolve(stdout);
    });
  });
});

// Other IPC Handlers
ipcMain.handle('close-app', () => {
  app.quit()
})

ipcMain.handle('ssh-connect', async (event, { username, host, port }) => {
  console.error(username, host, port)
  const { spawn } = require('child_process')
  const command = `ssh ${username}@${host} -p ${port};read`
  
  try {
    const terminal = spawn('gnome-terminal', ['--', 'bash', '-c', command], {
      detached: true,
      stdio: 'ignore'
    })
    
    terminal.unref()
    return { success: true }
  } catch (error) {
    console.error('SSH connection failed:', error)
    return { success: false, error: error.response?.data?.error || `SSH connection failed: ${error.message}` }
  }
})