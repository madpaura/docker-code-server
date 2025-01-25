const { app, BrowserWindow, ipcMain, Menu, Tray } = require('electron')
const fs = require('fs')
const axios = require('axios')
axios.defaults.debug = false
const path = require('path')

let mainWindow
let tray = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    frame: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    }
  })

  mainWindow.loadFile('index.html')
  
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

// IPC Handlers
ipcMain.handle('close-app', () => {
  app.quit()
})

ipcMain.handle('get-container-info', async (event, containerId) => {
  try {
    const response = await axios.get(`http://localhost:8511/api/containers/${containerId}`)
    return response.data
  } catch (error) {
    console.error('Error fetching containers:', error.response?.data?.error || error.message)
    throw new Error(error.response?.data?.error || 'Failed to fetch containers')
  }
})

ipcMain.handle('get-container-stats', async (event, containerId) => {
  try {
    const response = await axios.get(`http://localhost:8511/api/containers/${containerId}/stats`)
    return response.data
  } catch (error) {
    console.error('Error fetching container stats:', error.response?.data?.error || error.message)
    throw new Error(error.response?.data?.error || 'Failed to fetch container stats')
  }
})

ipcMain.handle('container-action', async (event, { action, containerId }) => {
  try {
    const response = await axios.post(`http://localhost:8511/api/containers/${containerId}/${action}`)
    return response.data
  } catch (error) {
    console.error(`Error performing ${action}:`, error.response?.data?.error || error.message)
    throw new Error(error.response?.data?.error || `Failed to perform ${action}`)
  }
})

ipcMain.handle('generate-user-hash', async (event, username) => {
  const crypto = require('crypto')
  const hash = crypto.createHash('sha256').update(username).digest('hex')
  return hash.substring(0, 16)
})

ipcMain.handle('container-create', async (event, username) => {
  try {
    const response = await axios.post('http://localhost:8511/api/containers', {
      user: username,
      session_token: 'TODO', // TODO: Get actual session token
    })
    return response.data
  } catch (error) {
    console.error('Error creating container:', error.response?.data?.error || error.message)
    throw new Error(error.response?.data?.error || 'Failed to create container')
  }
})

ipcMain.handle('ssh-connect', async (event, { username, host, port }) => {
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
    throw new Error(`SSH connection failed: ${error.message}`)
  }
})