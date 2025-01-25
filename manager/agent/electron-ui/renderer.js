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
const closeBtn = document.getElementById('close-btn')

// Handle close button click
if (closeBtn) {
  closeBtn.addEventListener('click', () => {
    window.electronAPI.closeApp()
  })
}

let currentContainerId = null
let refreshInterval = null
const containerSelect = document.getElementById('container-select')


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

// Initialize Plotly gauges
const createGauge = (value, title, color = 'royalblue') => {
  return {
    value: value,
    title: { text: title },
    gauge: {
      axis: { range: [0, 100] },
      bar: { color },
      steps: [
        { range: [0, 50], color: 'lightgreen' },
        { range: [50, 80], color: 'orange' },
        { range: [80, 100], color: 'orangered' }
      ]
    }
  }
}

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
        .progress-container {
          margin: 5px 0;
        }
        .progress-label {
          font-size: 12px;
          margin-bottom: 2px;
        }
        .progress-bar {
          height: 15px;
          background-color: #e0e0e0;
          border-radius: 8px;
          overflow: hidden;
          position: relative;
        }
        .progress {
          height: 100%;
          background-color: #007bff;
          transition: width 0.3s ease;
          text-align: right;
          padding-right: 3px;
          color: white;
          font-size: 10px;
          line-height: 15px;
        }
      </style>
      <div class="space-y-2">
        <div class="progress-container">
          <div class="progress-label">CPU Usage</div>
          <div class="progress-bar">
            <div id="cpu-progress" class="progress" style="width: ${cpuUsage}%">${cpuUsage.toFixed(1)}%</div>
          </div>
        </div>
        <div class="progress-container">
          <div class="progress-label">Memory Usage</div>
          <div class="progress-bar">
            <div id="memory-progress" class="progress" style="width: ${memoryUsage}%">${memoryUsage.toFixed(1)}%</div>
          </div>
        </div>
        <div>Memory Used: ${memoryUsed.toFixed(2)} MB</div>
        <div>Memory Limit: ${memoryLimit.toFixed(2)} MB</div>
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
    if (action == 'create') {
      const response = await window.electronAPI.containerCreate('vishwa')

      if (response.success) {
        alert(`Container created successfully: ${response.container.name}`)
        await fetchContainers()
      }
    } else {
      await window.electronAPI.containerAction(action, currentContainerId)
      updateStats()
    }
  } catch (error) {
    console.error(`Error performing ${action}:`, error)
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

  // Fetch available containers
  await fetchContainers()

  // Set initial container if available
  if (containerSelect.options.length > 0) {
    currentContainerId = containerSelect.value
    updateStats()
    refreshInterval = setInterval(updateStats, 75000)
  }
}

// Cleanup on window close
window.addEventListener('beforeunload', () => {
  clearInterval(refreshInterval)
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
  
  switch(service) {
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
      const ports = {
        vscode: info.container.Ports.find(p => p.PrivatePort === 8080).PublicPort,
        ssh: info.container.Ports.find(p => p.PrivatePort === 22).PublicPort,
        rdp: info.container.Ports.find(p => p.PrivatePort === 3389).PublicPort,
        fm: info.container.Ports.find(p => p.PrivatePort === 3000).PublicPort
      }

      // Update service URLs/commands
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