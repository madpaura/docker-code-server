# add current user to docker group
```
sudo gpasswd -a $USER docker
newgrp docker
docker ps
```
# update qemubuild
```
vi qemu/pc-bios/keymaps/meson.build 
'ar': '-l ar', -->  'ar': '-l ara',
```

# update opencxl-core, change pcap file
```
vi  opencxl-core/pyproject.toml 
python-libpcap = "^0.4.2" --> python-libpcap = "^0.5.2"
```

# Setup GuestOS base directory, contains all base images (mounted as read only)
```.
├── guestos_base
│   ├── centos
│   └── fedora
```

# setup template directory
```bash
.
├── code    # vsode related
│   └── config
│       └── extensions # extensions
├── guestos  # overlay will be created here
└── tools
    └── ARMCompiler6.16
        ├── bin
        ├── include
        ├── lib
        ├── license_terms
        └── sw
```

# setup mysql
execute scripts/mysql.sh

# setup kvm permission
```
chmod 777 /dev/kvm
```

# docker pull

```
 docker pull 107.110.39.183:5000/cxl.io/dev/code-server:latest
 ```
 

 # Setup tools download folder under agent directory for user to download
 