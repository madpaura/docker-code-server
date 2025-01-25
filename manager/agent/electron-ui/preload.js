const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  getContainerStats: (containerId) => ipcRenderer.invoke('get-container-stats', containerId),
  getContainerInfo: (containerId) => ipcRenderer.invoke('get-container-info', containerId),
  containerAction: (action, containerId) => ipcRenderer.invoke('container-action', { action, containerId }),
  containerCreate: (username) => ipcRenderer.invoke('container-create', username),
  generateUserHash: (username) => ipcRenderer.invoke('generate-user-hash', username),
  closeApp: () => ipcRenderer.invoke('close-app'),
  on: (channel, callback) => {
    ipcRenderer.on(channel, (event, ...args) => callback(...args))
  }
})