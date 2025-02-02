async function connectRDP(host, port, password) {
    try {
        const result = await window.electron.invoke('rdp-connect', { host, port, password });
        
        if (!result.success) {
            if (result.needsInstallation) {
                // The helper has already shown the installation prompt
                console.log('Remote Viewer installation required');
                return;
            }
            throw new Error(result.error || 'Failed to connect to RDP');
        }
    } catch (error) {
        console.error('RDP connection error:', error);
        // Handle the error appropriately in your UI
        throw error;
    }
}

module.exports = { connectRDP };
