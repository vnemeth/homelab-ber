# homelab-ber

Configuration for my Berlin homelab. This README describes the server itself and is
updated as the setup evolves. Service definitions live in [`stacks/`](stacks/).

## Hardware

| Component | Details                       |
| --------- | ----------------------------- |
| Model     | Lenovo ThinkCentre M80q Gen 3 |
| RAM       | 8 GB                          |
| Storage   | 256 GB SSD                    |

## Operating system

- Minimal Debian installation
- Lightweight Xfce desktop
- Hostname: `lab`
- Domain: `local.ber.nvcode.com` (FQDN `lab.local.ber.nvcode.com`)
- Debian version: 13.7 (trixie)

## Storage

GPT disk booted in UEFI mode, with LVM on top. The disk is fully allocated; there is no
full-disk encryption, so the server comes back up unattended after a power cut.

| Device         | Partition / LV       | Size                       | FS    | Label    | Mount             |
| -------------- | -------------------- | -------------------------- | ----- | -------- | ----------------- |
| `nvme0n1p1`    | EFI System Partition | 1 GiB                      | FAT32 | —        | `/boot/efi`       |
| `nvme0n1p2`    | Boot                 | 1 GiB                      | ext4  | —        | `/boot`           |
| `nvme0n1p3`    | LVM PV → VG `vg0`    | remaining space            | —     | —        | —                 |
| `vg0-root`     | ↳ `root` LV          | 40 GiB                     | ext4  | `root`   | `/`               |
| `vg0-docker`   | ↳ `docker` LV        | 70 GiB                     | ext4  | `docker` | `/var/lib/docker` |
| `vg0-data`     | ↳ `data` LV          | remaining space (~126 GiB) | ext4  | `data`   | `/data`           |

`/home` and `/srv` share the `data` volume through bind mounts:

| Source       | Mount   |
| ------------ | ------- |
| `/data/home` | `/home` |
| `/data/srv`  | `/srv`  |

- **`/`** holds the OS. The clone of this repo (`/opt/homelab-ber`), whose `stacks/`
  folder is Dockge's stacks directory, lives here too.
- **`/var/lib/docker`** holds images, container layers and logs, which can all be
  re-downloaded. Keeping them on their own volume means they can't fill up the OS.
  `docker system prune` frees space here.
- **`/srv`** holds persistent service data. Each stack bind-mounts `/srv/<stack>/`.
- **`/home`** shares space with `/srv`, so large files in the home directory don't eat
  into the OS volume.

There is no disk swap. Swap is provided by zram (compressed swap in RAM).

## Network

- Connection: Wi-Fi on the onboard Intel adapter (`wlo1`), to a Telekom Speedport router
- IPv4: `192.168.2.30`, a DHCP reservation for the adapter's MAC address on the router
- Remote desktop: RDP via xrdp on port 3389, home network only
- Services: `https://<service>.local.ber.nvcode.com`, through Traefik with a Let's Encrypt
  wildcard certificate for `*.local.ber.nvcode.com`
- DNS: `nvcode.com` is hosted at DreamHost, which has these public records:

  | Name                           | Type  | Value                      |
  | ------------------------------ | ----- | -------------------------- |
  | `lab.local.ber.nvcode.com`     | A     | `192.168.2.30`             |
  | `dockge.local.ber.nvcode.com`  | CNAME | `lab.local.ber.nvcode.com` |
  | `traefik.local.ber.nvcode.com` | CNAME | `lab.local.ber.nvcode.com` |
  | `auth.local.ber.nvcode.com`    | CNAME | `lab.local.ber.nvcode.com` |

  Each new service gets a CNAME pointing at `lab.local.ber.nvcode.com`.

## Container platform

- All services run in Docker containers.
- Docker Compose stacks are managed with [Dockge](https://github.com/louislam/dockge), at
  `https://dockge.local.ber.nvcode.com` (fallback: `http://192.168.2.30:5001`).
- [Traefik](https://traefik.io/) is the reverse proxy for all web interfaces. Stacks join
  the external Docker network `proxy` and are routed by Docker labels.
- This repo is cloned to `/opt/homelab-ber` on the server, and Dockge's stacks directory
  is its `stacks/` folder, so stacks edited in Dockge show up in `git status`. Dockge runs
  as root, so files it creates are owned by root; fix with
  `sudo chown -R valentin:valentin /opt/homelab-ber` before committing.
- Each stack is a folder under [`stacks/`](stacks/) containing a `compose.yaml` and,
  where needed, a `.env.example`. To deploy, copy it to `.env` on the server and fill in
  the real values. `.env` files are git-ignored and never committed.

## Repository layout

```
.
├── .gitignore    # Keeps real .env files out of git
├── README.md     # Server configuration (this file)
├── AGENTS.md     # Instructions for AI coding agents working in this repo
└── stacks/       # One folder per Docker Compose stack, managed by Dockge
```

## Stacks

| Stack | Purpose | Port(s) | Notes |
| ----- | ------- | ------- | ----- |
| `dockge` | Manages the Docker Compose stacks | 5001 | `dockge.local.ber.nvcode.com`; data in `/srv/dockge` |
| `traefik` | Reverse proxy and TLS | 80, 443 | Dashboard at `traefik.local.ber.nvcode.com`; certificates in `/srv/traefik/acme` |
| `authentik` | Single sign-on and forward auth | — | `auth.local.ber.nvcode.com`; data in `/srv/authentik`. Memory-heavy: about 1–1.5 GB with PostgreSQL |

## Setup log

Steps performed on the server, in order. Append new entries as they happen.

### 1. Install Debian

Use the **netinst** image (not a live image, which installs a full desktop) and boot it in
UEFI mode. The onboard Intel Wi-Fi adapter is detected out of the box; no extra firmware
is needed.

**Network:** hostname `lab`, domain name `local.ber.nvcode.com`.

**Partitioning** (choose *Manual*):

1. Create a GPT partition table.
2. Create the partitions:
   - 1 GiB, *EFI System Partition*
   - 1 GiB, ext4, mount point `/boot`
   - all remaining space, *physical volume for LVM*
3. *Configure the Logical Volume Manager*: create volume group `vg0` on the LVM
   partition, then the logical volumes:
   - `root`, 40 GiB
   - `docker`, 70 GiB
   - `data`, all remaining space
4. Set each logical volume to ext4 with its mount point, and give it a label matching its
   name: `root` → `/`, `docker` → `/var/lib/docker`, `data` → `/data` (*Enter manually*).
5. Don't create swap. Confirm the warning about missing swap.

**Software selection:** tick only *SSH server* and *standard system utilities*; untick
every desktop.

**Users:** set a root password and create the user `valentin` (Valentin Nemeth). Because a
root password is set, the installer doesn't install `sudo`.

### 2. Fix DHCP on the Speedport router

Out of the box, `wlo1` only gets a link-local `169.254.x.x` address: the Telekom Speedport
doesn't answer `dhcpcd`'s default DUID-based client ID. Configure `dhcpcd` to identify
itself with the MAC address instead. As root (`su -`):

```bash
# /etc/dhcpcd.conf: enable "clientid", comment out "duid"
# (if the file doesn't exist, create it with just the line "clientid")
sed -i 's/^duid/#duid/; s/^#clientid/clientid/' /etc/dhcpcd.conf
grep -nE '^#?(duid|clientid)' /etc/dhcpcd.conf

ifdown wlo1 && ifup wlo1
ip -br addr show wlo1
```

`wlo1` should now have its reserved address, `192.168.2.30`.

### 3. Set up passwordless `sudo` for `valentin`

As root (`su -`):

```bash
apt install sudo
usermod -aG sudo valentin
echo 'valentin ALL=(ALL:ALL) NOPASSWD: ALL' > /etc/sudoers.d/valentin
chmod 0440 /etc/sudoers.d/valentin
visudo -c    # must report "parsed OK"
```

Log out and back in as `valentin` for the group change to apply, then check:

```bash
sudo -n true && echo "passwordless sudo works"
```

Once `sudo` works, lock the root account so it can't be logged into directly:

```bash
sudo passwd -l root
```

### 4. Move `/home` and `/srv` onto the data volume

The installer can't create bind mounts, so this is done after the first boot, on the text
console, before the desktop is installed. Run it from `/` so the shell isn't using the
home directory.

```bash
cd /

# Copy the home directory created by the installer onto the data volume
sudo apt install rsync    # if it's not already installed
sudo mkdir -p /data/home /data/srv
sudo rsync -aAX /home/ /data/home/

# Keep the original as a fallback and create empty mount points
sudo mv /home /home.old
sudo mkdir /home /srv

# Add the bind mounts; they wait until /data is mounted
sudo tee -a /etc/fstab <<'EOF'
/data/home  /home  none  bind,x-systemd.requires-mounts-for=/data  0 0
/data/srv   /srv   none  bind,x-systemd.requires-mounts-for=/data  0 0
EOF

sudo systemctl daemon-reload
sudo mount -a
sudo reboot
```

After the reboot, check the mounts and that the home directory is intact, then remove the
fallback copy:

```bash
findmnt /data /home /srv    # sources: vg0-data, vg0-data[/home], vg0-data[/srv]
ls ~
sudo rm -rf /home.old
```

### 5. Set up zram swap

```bash
sudo apt install zram-tools
```

In `/etc/default/zramswap`, set:

```
ALGO=zstd
PERCENT=50
```

Swapping to zram is cheap, so raise the kernel's swappiness from the default of 60:

```bash
echo 'vm.swappiness=100' | sudo tee /etc/sysctl.d/99-zram.conf
sudo sysctl --system
sudo systemctl restart zramswap
```

Check that it's active with `swapon --show` (it should list `/dev/zram0`).

### 6. Install a minimal Xfce desktop

Stop `apt` from installing recommended packages, so the system stays minimal. Extras are
installed explicitly when needed:

```bash
echo 'APT::Install-Recommends "false";' | sudo tee /etc/apt/apt.conf.d/99no-recommends
```

Install only the core of Xfce, a terminal, the display manager and the X server.
`xorg` and `lightdm-gtk-greeter` are only *recommended* by Xfce and LightDM, so with
recommends turned off they must be listed explicitly, or the desktop won't start:

```bash
sudo apt install xfce4 xfce4-terminal lightdm lightdm-gtk-greeter xorg
sudo reboot
```

Mark the packages the server can't run without as manually installed, so an `autoremove`
can never take them away (networking, SSH and the desktop):

```bash
sudo apt-mark manual wpasupplicant dhcpcd-base firmware-iwlwifi ifupdown openssh-server \
  xorg lightdm-gtk-greeter xfce4 xfce4-terminal lightdm
```

**Removing extras that were already installed.** Packages installed before recommends
were turned off stay on the system. To list everything that's only installed because
another package recommends it, and then remove it:

```bash
sudo apt autoremove -s -o APT::AutoRemove::RecommendsImportant=false   # dry run: review the list
sudo apt autoremove -o APT::AutoRemove::RecommendsImportant=false
```

Run the `apt-mark manual` command above first, so the cleanup doesn't remove the
networking or desktop packages.

### 7. Set up remote desktop (xrdp)

xrdp serves the Xfce desktop over RDP on port 3389. Each RDP connection gets its own
desktop session. With recommends turned off, the Xorg backend `xorgxrdp` must be listed
explicitly:

```bash
sudo apt install xrdp xorgxrdp
sudo apt-mark manual xrdp xorgxrdp

# Start Xfce for RDP sessions
echo xfce4-session > ~/.xsession

# Give xrdp access to its TLS certificate
sudo adduser xrdp ssl-cert
sudo systemctl enable --now xrdp
sudo systemctl restart xrdp

# Check it's listening
sudo ss -tlnp | grep 3389
```

Connect from the Mac with **Windows App** (App Store) to `192.168.2.30`, as `valentin`.

- Log out of the local Xfce session first. If `valentin` is still logged in on the
  machine's own screen, the RDP session opens to a black screen and closes.
- RDP is for the home network only. Port 3389 is not forwarded on the router.

### 8. Install Google Chrome

Google's `.deb` also adds Google's apt repository, so Chrome updates with
`sudo apt upgrade`:

```bash
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb
```

Chrome is memory-heavy for an 8 GB host shared with Docker; close it when not in use.

### 9. Install Docker Engine and Compose

From Docker's own apt repository. With recommends turned off, the helpers Docker needs
are listed explicitly:

```bash
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
  docker-compose-plugin iptables apparmor pigz git
```

Cap container logs, so they can't fill the Docker volume:

```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
sudo systemctl restart docker
```

Let `valentin` use Docker without `sudo` (log out and back in afterwards):

```bash
sudo usermod -aG docker valentin
```

Check:

```bash
docker run --rm hello-world
docker compose version
docker info | grep -E 'Docker Root Dir|Logging Driver'   # /var/lib/docker, json-file
```

### 10. Clone this repo to `/opt/homelab-ber`

The server accesses GitHub with a deploy key that only grants access to this repo:

```bash
ssh-keygen -t ed25519 -C "lab deploy key for homelab-ber" -f ~/.ssh/homelab-ber -N ""
cat ~/.ssh/homelab-ber.pub
```

Add the public key on GitHub under the repo's *Settings → Deploy keys*, with
*Allow write access* ticked. Then point SSH at the key for GitHub by adding to
`~/.ssh/config` (mode `600`):

```
Host github.com
  IdentityFile ~/.ssh/homelab-ber
  IdentitiesOnly yes
```

Clone the repo:

```bash
sudo mkdir /opt/homelab-ber
sudo chown valentin:valentin /opt/homelab-ber
git clone git@github.com:vnemeth/homelab-ber.git /opt/homelab-ber
cd /opt/homelab-ber
git config user.name "Valentin Nemeth"
git config user.email "valentin@nvcode.com"
```

### 11. Start Dockge

Dockge's own stack is [`stacks/dockge/compose.yaml`](stacks/dockge/compose.yaml). Start it
once from the command line; after that it shows up in its own UI:

```bash
sudo mkdir -p /srv/dockge/data
cd /opt/homelab-ber/stacks/dockge
docker compose up -d
```

Open `http://192.168.2.30:5001` and create the admin account.

### 12. Set up Traefik with a wildcard certificate

Traefik gets a Let's Encrypt certificate for `local.ber.nvcode.com` and
`*.local.ber.nvcode.com` using the DNS challenge: it creates a temporary TXT record through
the DreamHost API.

1. In the DreamHost panel, under *Advanced → API*, create an API key with the functions
   `dns-list_records`, `dns-add_record` and `dns-remove_record`.
2. Create the shared Docker network and the certificate directory:

   ```bash
   docker network create proxy
   sudo mkdir -p /srv/traefik/acme
   ```

3. Create `stacks/traefik/.env` from [`.env.example`](stacks/traefik/.env.example) and
   fill in the API key and the dashboard login:

   ```bash
   cd /opt/homelab-ber/stacks/traefik
   cp .env.example .env
   docker run --rm httpd:2.4-alpine htpasswd -nbB valentin 'your-password'   # dashboard login
   ```

4. Start Traefik, then redeploy Dockge so it joins the `proxy` network:

   ```bash
   docker compose up -d
   docker compose logs -f    # wait for the certificate; DreamHost DNS can take minutes
   cd ../dockge && docker compose up -d
   ```

The certificate is stored in `/srv/traefik/acme/acme.json` and renewed automatically.

### 13. Set up authentik

authentik provides single sign-on. It runs as a server, a background worker and a
PostgreSQL database, and is served at `auth.local.ber.nvcode.com`. Its stack also defines
the Traefik forward-auth middleware `authentik@docker`.

1. At DreamHost, add the CNAME `auth.local.ber.nvcode.com` → `lab.local.ber.nvcode.com`.
2. Create the data directories. authentik runs as UID 1000:

   ```bash
   sudo mkdir -p /srv/authentik/postgres /srv/authentik/data /srv/authentik/custom-templates
   sudo chown 1000:1000 /srv/authentik/data /srv/authentik/custom-templates
   ```

3. Create `stacks/authentik/.env` from [`.env.example`](stacks/authentik/.env.example),
   with generated values for `PG_PASS` and `AUTHENTIK_SECRET_KEY`.
4. Start it and run the initial setup:

   ```bash
   cd /opt/homelab-ber/stacks/authentik
   docker compose up -d
   ```

   Open `https://auth.local.ber.nvcode.com/if/flow/initial-setup/` and set the password
   for the `akadmin` user.
