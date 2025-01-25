import os
import requests
from PIL import Image
from io import BytesIO

# Create assets directory if it doesn't exist
assets_dir = 'manager/agent/electron-ui/assets'
os.makedirs(assets_dir, exist_ok=True)

# Icon names and their corresponding Bootstrap icon names
icons = {
    'create.png': 'plus-circle',
    'start.png': 'play-circle', 
    'stop.png': 'stop-circle',
    'restart.png': 'arrow-repeat',
    'remove.png': 'trash',
    'vscode.png': 'code-square',
    'ssh.png': 'terminal',
    'rdp.png': 'display',
    'fm.png': 'hdd-network'
}

# Base URL for Bootstrap icons
base_url = 'https://raw.githubusercontent.com/twbs/icons/main/icons/{}.svg'

# Download and convert each icon
for filename, icon_name in icons.items():
    print(f'Downloading {icon_name}...')
    
    # Download SVG from GitHub
    response = requests.get(base_url.format(icon_name))
    response.raise_for_status()
    
    # Convert SVG to PNG and resize
    from cairosvg import svg2png
    png_data = svg2png(bytestring=response.content, output_width=32, output_height=32)
    
    # Save PNG file
    with open(os.path.join(assets_dir, filename), 'wb') as f:
        f.write(png_data)

print('All icons downloaded successfully!')