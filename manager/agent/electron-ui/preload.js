const { contextBridge, ipcRenderer, shell } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // Auth related
  login: (username, password) => ipcRenderer.invoke('login', { username, password }),
  validateSession: (userId, sessionToken) => ipcRenderer.invoke('validate-session', { userId, sessionToken }),
  logout: (userId) => ipcRenderer.invoke('logout', { userId }),
  getUserInfo: (userId) => ipcRenderer.invoke('get-user-info', { userId }),

  // Container related
  setContainerApi: (ip, port) => ipcRenderer.invoke('set-container-api', { ip, port }),
  getContainerStats: (containerId) => ipcRenderer.invoke('get-container-stats', containerId),
  getContainerInfo: (containerId) => ipcRenderer.invoke('get-container-info', containerId),
  containerAction: (action, containerId) => ipcRenderer.invoke('container-action', { action, containerId }),
  containerCreate: (username, sessionToken) => ipcRenderer.invoke('container-create', username, sessionToken),
  getContainerPorts: (containerId) => ipcRenderer.invoke('get-container-ports', containerId),

  // Other
  generateUserHash: (username) => ipcRenderer.invoke('generate-user-hash', username),
  closeApp: () => ipcRenderer.invoke('close-app'),
  sshConnect: (username, host, port) => ipcRenderer.invoke('ssh-connect', { username, host, port }),
  openExternal: (url) => shell.openExternal(url),
  launchRemoteViewer: (host, port) => ipcRenderer.invoke('launch-remote-viewer', { host, port }),
  on: (channel, callback) => {
    ipcRenderer.on(channel, (event, ...args) => callback(...args))
  }
})