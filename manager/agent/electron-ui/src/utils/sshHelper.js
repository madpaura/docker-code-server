const { spawn } = require('child_process');
const os = require('os');
const path = require('path');

class SSHHelper {
    static isWindows() {
        return os.platform() === 'win32';
    }

    static async launchSSH(username, host, port) {
        try {
            if (this.isWindows()) {
                return this.launchPutty(username, host, port);
            } else {
                return this.launchTerminal(username, host, port);
            }
        } catch (error) {
            console.error('SSH launch failed:', error);
            throw error;
        }
    }

    static launchPutty(username, host, port) {
        try {
            // Default PuTTY locations to check
            const puttyPaths = [
                path.join(process.env['ProgramFiles'], 'PuTTY', 'putty.exe'),
                path.join(process.env['ProgramFiles(x86)'], 'PuTTY', 'putty.exe'),
                'putty.exe' // If in PATH
            ];

            // Find the first available PuTTY executable
            const puttyExe = puttyPaths.find(p => {
                try {
                    require('fs').accessSync(p);
                    return true;
                } catch {
                    return false;
                }
            }) || 'putty.exe';

            const args = [
                '-ssh',
                `${username}@${host}`,
                '-P',
                `${port}`
            ];

            const putty = spawn(puttyExe, args, {
                detached: true,
                stdio: 'ignore',
                windowsHide: false
            });

            putty.unref();
            return { success: true };
        } catch (error) {
            console.error('PuTTY launch failed:', error);
            return {
                success: false,
                error: `Failed to launch PuTTY: ${error.message}`
            };
        }
    }

    static launchTerminal(username, host, port) {
        try {
            const command = `ssh ${username}@${host} -p ${port};read`;
            const terminal = spawn('gnome-terminal', ['--', 'bash', '-c', command], {
                detached: true,
                stdio: 'ignore'
            });
            
            terminal.unref();
            return { success: true };
        } catch (error) {
            console.error('Terminal launch failed:', error);
            return {
                success: false,
                error: `Failed to launch terminal: ${error.message}`
            };
        }
    }
}

module.exports = SSHHelper;
