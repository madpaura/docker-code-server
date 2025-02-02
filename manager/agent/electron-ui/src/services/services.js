const { ipcMain } = require('electron');
const { shell } = require('electron');

function setupServiceHandlers() {
    ipcMain.handle('vscode-connect', async (event, { host, port }) => {
        try {
            const url = `http://${host}:${port}`;
            await shell.openExternal(url);
            return { success: true };
        } catch (error) {
            console.error('VS Code connection failed:', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('ssh-connect', async (event, { username, host, port }) => {
        const { spawn } = require('child_process');
        const command = `ssh ${username}@${host} -p ${port};read`;
        
        try {
            const terminal = spawn('gnome-terminal', ['--', 'bash', '-c', command], {
                detached: true,
                stdio: 'ignore'
            });
            
            terminal.unref();
            return { success: true };
        } catch (error) {
            console.error('SSH connection failed:', error);
            return { 
                success: false, 
                error: error.response?.data?.error || `SSH connection failed: ${error.message}` 
            };
        }
    });

    ipcMain.handle('rdp-connect', async (event, { host, port }) => {
        const { spawn } = require('child_process');
        try {
            const viewer = spawn('remote-viewer', [`spice://${host}:${port}`], {
                detached: true,
                stdio: 'ignore'
            });
            viewer.unref();
            return { success: true };
        } catch (error) {
            console.error('RDP connection failed:', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fm-connect', async (event, { host, port }) => {
        try {
            const url = `http://${host}:${port}`;
            await shell.openExternal(url);
            return { success: true };
        } catch (error) {
            console.error('File Manager connection failed:', error);
            return { success: false, error: error.message };
        }
    });
}

module.exports = {
    setupServiceHandlers
};
