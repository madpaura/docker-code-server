// Generate container name from username
const getContainerName = async (username) => {
  const hash = await window.electronAPI.generateUserHash(username)
  return `code-server-${username}-${hash}`
}

const cpuGauge = document.getElementById('cpu-gauge')
const memoryGauge = document.getElementById('memory-gauge')
const containerInfo = document.getElementById('container-info')
const actionButtons = document.querySelectorAll('.btn-action')
const serviceButtons = document.querySelectorAll('.service-btn')
const serviceInfoSection = document.getElementById('service-info')
const serviceTitle = document.getElementById('service-title')
const serviceContent = document.getElementById('service-content')

let currentContainerId = null
let refreshInterval = null
let containerState = {
  exists: false,
  running: false
}
const containerSelect = document.getElementById('container-select')
const createButton = document.getElementById('create-btn')
const startStopButton = document.getElementById('start-btn')
const removeButton = document.getElementById('remove-btn')

const updateButtonStates = () => {
  console.log('Updating button states:', containerState)

  try {
    // Show/hide create button
    createButton.style.display = containerState.exists ? 'none' : 'block'
    createButton.disabled = containerState.exists

    // Show/hide action buttons based on container existence
    const actionButtons = document.querySelectorAll('.btn-action')
    actionButtons.forEach(btn => {
      btn.style.display = containerState.exists ? 'block' : 'none'
    })

    // Update start/stop button
    if (containerState.exists) {
      startStopButton.disabled = false
      startStopButton.innerHTML = containerState.running ?
        '<i class="bi bi-stop-circle text-red-600"></i>' :
        '<i class="bi bi-play-circle text-green-600"></i>'
      startStopButton.title = containerState.running ? 'Stop Container' : 'Start Container'
    }

    // Update remove button state
    removeButton.disabled = !containerState.exists || containerState.running

    // Update restart button state
    const restartButton = document.getElementById('restart-btn')
    if (restartButton) {
      restartButton.disabled = !containerState.exists || !containerState.running
    }
  } catch (error) {
    console.error('Error updating button states:', error)
  }
}

// Add periodic state refresh
const refreshContainerState = async () => {
  try {
    const container_name = await getContainerName('vishwa')
    const response = await window.electronAPI.getContainerInfo(container_name)

    if (response && response.container) {
      const containers = Array.isArray(response.container) ? response.container : [response.container]
      containerState.exists = containers.length > 0
      containerState.running = containers.some(c => c.State === 'running')
      updateButtonStates()
    }
  } catch (error) {
    console.error('Error refreshing container state:', error)
  }
}

// Initialize periodic refresh
let stateRefreshInterval = null

// Fetch available containers
const fetchContainers = async () => {
  try {
    const container_name = await getContainerName('vishwa')
    const response = await window.electronAPI.getContainerInfo(container_name)
    console.log('Container Info Response:', response)

    if (!response || !response.container) {
      throw new Error('Invalid container info response')
    }

    const containers = Array.isArray(response.container) ? response.container : [response.container]

    console.log(containers)

    containerSelect.innerHTML = containers
      .map(container => {
        // Extract username from container name (format: code-server-username-hash)
        const nameParts = container.name.split('-')
        const username = nameParts.length >= 3 ? nameParts[2] : 'unknown'
        return `<option value="${container.id}">${container.name}</option>`
      })
      .join('')

    // Update container state
    containerState.exists = containers.length > 0
    containerState.running = containers.some(c => c.State === 'running')
    updateButtonStates()
  } catch (error) {
    console.error('Error fetching containers:', error)
  }
}

// Handle container selection change
containerSelect.addEventListener('change', (e) => {
  currentContainerId = e.target.value
  if (refreshInterval) clearInterval(refreshInterval)
  updateStats()
  updateServiceConnections()
  refreshInterval = setInterval(updateStats, 5000)
})

// Update container stats
const updateStats = async () => {
  try {
    const container_name = await getContainerName('vishwa')

    const response = await window.electronAPI.getContainerStats(container_name)
    console.log('Container Stats:', JSON.stringify(response, null, 2))

    if (!response) {
      throw new Error('No stats received from container')
    }

    const stats = response.stats

    const cpuUsage = stats.cpu_usage || 0
    const memoryUsage = stats.memory_usage || 0
    const memoryUsed = stats.memory_used || 0
    const memoryLimit = stats.memory_limit || 0

    // Update progress bars
    const cpuProgress = document.getElementById('cpu-progress')
    const memoryProgress = document.getElementById('memory-progress')

    if (cpuProgress) {
      cpuProgress.style.width = `${cpuUsage}%`
      cpuProgress.textContent = `${cpuUsage.toFixed(1)}%`
    }

    if (memoryProgress) {
      memoryProgress.style.width = `${memoryUsage}%`
      memoryProgress.textContent = `${memoryUsage.toFixed(1)}%`
    }

    containerInfo.innerHTML = `
    <style>
      .metrics-container {
        padding: 0.5rem 0;
      }
      
      .metric-item {
        margin-bottom: 1.5rem;
      }
      
      .progress-label {
        color: rgba(0, 0, 0, 0.87);
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .progress-label span {
        color: rgba(0, 0, 0, 0.6);
        font-size: 0.75rem;
      }
      
      .progress-track {
        height: 4px;
        background-color: rgba(0, 0, 0, 0.08);
        border-radius: 2px;
        overflow: hidden;
        position: relative;
      }
      
      .progress-bar {
        height: 100%;
        background-color: #1976d2;
        position: absolute;
        top: 0;
        left: 0;
        transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      }
      
      .memory-stats {
        display: flex;
        justify-content: space-between;
        margin-top: 2rem;
        color: rgba(0, 0, 0, 0.6);
        font-size: 0.875rem;
      }
    </style>
    
    <div class="metrics-container">
      <div class="metric-item">
        <div class="progress-label">
          CPU Usage
          <span>${cpuUsage.toFixed(1)}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-bar" style="width: ${cpuUsage}%"></div>
        </div>
      </div>
      
      <div class="metric-item">
        <div class="progress-label">
          Memory Usage
          <span>${memoryUsage.toFixed(1)}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-bar" style="width: ${memoryUsage}%"></div>
        </div>
      </div>
      
      <div class="memory-stats">
        <div>Used: ${memoryUsed.toFixed(2)} MB</div>
        <div>Total: ${memoryLimit.toFixed(2)} MB</div>
      </div>
    </div>
  `
  } catch (error) {
    console.error('Error updating stats:', error)
  }
}

// Show about information
const showAbout = () => {
  serviceInfoSection.classList.remove('hidden')
  serviceTitle.textContent = 'About'
  serviceContent.innerHTML = `
    <div class="mb-2">This is the CXL Remote Development interface.</div>
    <div class="mb-2">Version: 1.0.0</div>
    <div>Placeholder for about information</div>
  `
}

// Handle container actions
const handleContainerAction = async (action) => {
  try {
    if (action === 'create') {
      const response = await window.electronAPI.containerCreate('vishwa')
      if (response.success) {
        alert(`Container created successfully: ${response.container.name}`)
        containerState.exists = true
        containerState.running = false
        await fetchContainers()
      }
    } else {
      const wasRunning = containerState.running
      await window.electronAPI.containerAction(action, currentContainerId)

      // Update state based on action
      if (action === 'start') {
        containerState.running = true
        updateStats()
      } else if (action === 'stop') {
        containerState.running = false
        updateStats()
      } else if (action === 'remove') {
        containerState.exists = false
        containerState.running = false
      }

      // Provide user feedback
      const actionMap = {
        start: { success: 'Container started successfully', error: 'Failed to start container' },
        stop: { success: 'Container stopped successfully', error: 'Failed to stop container' },
        remove: { success: 'Container removed successfully', error: 'Failed to remove container' }
      }

      if (action !== 'remove') {
        const success = containerState.running === (action === 'start')
        const message = success ? actionMap[action].success : actionMap[action].error
        alert(message)
      }

      updateButtonStates()
    }
  } catch (error) {
    console.error(`Error performing ${action}:`, error)
    // Reset state if action fails
    if (action === 'start' || action === 'stop') {
      containerState.running = wasRunning
    }
    alert(`Error: ${error.message}`)
  }
}

// Setup event listeners
const aboutButton = document.getElementById('about-btn')
if (aboutButton) {
  aboutButton.addEventListener('click', showAbout)
}

actionButtons.forEach(button => {
  button.addEventListener('click', () => {
    const action = button.id.replace('-btn', '')
    handleContainerAction(action)
  })
})

// Handle create container form submission
const handleCreateContainer = async (e) => {
  e.preventDefault()

  try {
    const response = await window.electronAPI.createContainer({
      username: 'vishwa',
    })

    if (response.success) {
      alert(`Container created successfully: ${response.container.name}`)
      await fetchContainers()
    } else {
      throw new Error(response.error || 'Failed to create container')
    }
  } catch (error) {
    alert(`Error creating container: ${error.message}`)
    console.error('Create container error:', error)
  }
}

// Initialize app
const init = async () => {
  // Setup create container form
  const createForm = document.getElementById('create-container-form')
  if (createForm) {
    createForm.addEventListener('submit', handleCreateContainer)
  }

  // Initialize buttons
  updateButtonStates()

  // Fetch available containers
  await fetchContainers()

  // Set initial container if available
  if (containerSelect.options.length > 0) {
    currentContainerId = containerSelect.value
    updateStats()
    refreshInterval = setInterval(updateStats, 75000)
  }

  refreshContainerState()

  // Start state refresh
  // stateRefreshInterval = setInterval(refreshContainerState, 10000)
}

// Cleanup intervals on window close
window.addEventListener('beforeunload', () => {
  clearInterval(refreshInterval)
  clearInterval(stateRefreshInterval)
})

// Handle service navigation
serviceButtons.forEach(button => {
  button.addEventListener('click', () => {
    const service = button.dataset.service
    showServiceInfo(service)
  })
})

// Handle system tray container actions
window.electronAPI.on('container-action', (action) => {
  handleContainerAction(action)
})

// Handle system tray service actions
window.electronAPI.on('service-action', (service) => {
  showServiceInfo(service)
})

// Handle SSH connection form submission
const handleSSHConnect = async () => {
  const status = document.getElementById('ssh-status')
  if (!status) return

  status.classList.remove('bg-red-100', 'text-red-700')
  status.classList.remove('bg-green-100', 'text-green-700')
  status.classList.add('bg-blue-100', 'text-blue-700')
  status.textContent = 'Connecting via SSH...'

  const host = '127.0.0.1'
  const port = 22
  const username = 'root'

  try {
    await window.electronAPI.sshConnect({ username, host, port })
    status.classList.add('bg-green-100', 'text-green-700')
    status.textContent = 'Connection successful!'
  } catch (error) {
    status.classList.add('bg-red-100', 'text-red-700')
    status.textContent = `Connection failed: ${error.message}`
  }
}

const showServiceInfo = (service) => {
  serviceInfoSection.classList.remove('hidden')

  switch (service) {
    case 'vscode':
      serviceTitle.textContent = 'VS Code Access'
      serviceContent.innerHTML = `
        <div class="mb-2">Use the following URL to access VS Code:</div>
        <div class="bg-gray-100 p-2 rounded">
          <code id="vscode-url"></code>
        </div>
      `
      break

    case 'ssh':
      serviceTitle.textContent = 'SSH Access'
      serviceContent.innerHTML = `
        <div class="space-y-4">
          <div>
            <div class="mb-2">Use the following command to connect via SSH:</div>
            <div class="bg-gray-100 p-2 rounded">
              <code id="ssh-command"></code>
            </div>
          </div>
          
          <div class="border-t pt-4">
            <div id="ssh-status" class="mt-4 p-3 rounded-md bg-blue-100 text-blue-700">
              Connecting via SSH...
            </div>
          </div>
          <script>
          </script>
        </div>
      `
      handleSSHConnect()
      break

    case 'rdp':
      serviceTitle.textContent = 'RDP Access'
      serviceContent.innerHTML = `
        <div class="mb-2">Use the following command to connect via RDP:</div>
        <div class="bg-gray-100 p-2 rounded">
          <code id="rdp-command"></code>
        </div>
      `
      break

    case 'fm':
      serviceTitle.textContent = 'FM UI Access'
      serviceContent.innerHTML = `
        <div class="mb-2">Use the following URL to access FM UI:</div>
        <div class="bg-gray-100 p-2 rounded">
          <code id="fm-url"></code>
        </div>
      `
      break

    case 'refresh':
      serviceTitle.textContent = 'Refresh'
      serviceContent.innerHTML = `
        <div class="mb-2">Refreshing container information...</div>
      `
      // Clear current container and refresh
      currentContainerId = null
      containerSelect.value = ''
      fetchContainers()
      break
  }

  // Update connection info when container changes
  updateServiceConnections()
}

const updateServiceConnections = () => {
  if (!currentContainerId) return

  // Get container IP and ports from electron API
  window.electronAPI.getContainerInfo(currentContainerId)
    .then(info => {
      const ip = info.container.NetworkSettings.IPAddress
      const getPort = (privatePort) =>
        info.container.Ports.find(p => p.PrivatePort === privatePort)?.PublicPort || 'N/A'

      // Update service URLs/commands
      const ports = {
        vscode: getPort(8080),
        ssh: getPort(22),
        rdp: getPort(3389),
        fm: getPort(3000)
      }
      if (document.getElementById('vscode-url')) {
        document.getElementById('vscode-url').textContent = `http://${ip}:${ports.vscode}`
      }
      if (document.getElementById('ssh-command')) {
        document.getElementById('ssh-command').textContent = `ssh root@${ip} -p ${ports.ssh}`
      }
      if (document.getElementById('rdp-command')) {
        document.getElementById('rdp-command').textContent = `xfreerdp /v:${ip}:${ports.rdp}`
      }
      if (document.getElementById('fm-url')) {
        document.getElementById('fm-url').textContent = `http://${ip}:${ports.fm}`
      }
    })
}

// Start the app
init()
