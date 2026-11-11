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
  | `beszel.local.ber.nvcode.com`  | CNAME | `lab.local.ber.nvcode.com` |
  | `wud.local.ber.nvcode.com`     | CNAME | `lab.local.ber.nvcode.com` |
  | `homeassistant.local.ber.nvcode.com` | CNAME | `lab.local.ber.nvcode.com` |
  | `zigbee2mqtt.local.ber.nvcode.com`   | CNAME | `lab.local.ber.nvcode.com` |
  | `homarr.local.ber.nvcode.com`  | CNAME | `lab.local.ber.nvcode.com` |
  | `musicassistant.local.ber.nvcode.com` | CNAME | `lab.local.ber.nvcode.com` |

  Each new service gets a CNAME pointing at `lab.local.ber.nvcode.com`.

  The Speedport's DNS rebind protection drops public DNS answers that point into the home
  network, so these names resolve to nothing on the LAN (the answer comes back empty).
  The router's rebind protection has an exception for `local.ber.nvcode.com`.

## Container platform

- All services run in Docker containers.
- Docker Compose stacks are managed with [Dockge](https://github.com/louislam/dockge), at
  `https://dockge.local.ber.nvcode.com`, behind authentik. Dockge's own login is turned off.
  Fallback if Traefik or authentik is down: `ssh -L 5001:localhost:5001 valentin@192.168.2.30`,
  then `http://localhost:5001`.
- Image tags follow one version line (e.g. `traefik:v3`, `postgres:16-alpine`), so Dockge's
  *Update* button pulls fixes within that line. New major versions, and new authentik
  releases, are deliberate tag changes in the repo.
- [Traefik](https://traefik.io/) is the reverse proxy for all web interfaces. Stacks join
  the external Docker network `proxy` and are routed by Docker labels.
- Containers can't resolve `*.local.ber.nvcode.com` through external DNS. Traefik
  carries `auth.local.ber.nvcode.com` as a network alias on `proxy`, so apps using
  authentik's OIDC login reach its token endpoint through Traefik.
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
├── .gitignore        # Keeps real .env files out of git
├── README.md         # Server configuration (this file)
├── AGENTS.md         # Instructions for AI coding agents working in this repo
├── HOMEASSISTANT.md  # Home Assistant's helpers, automations and dashboards
├── ZIGBEE.md         # The Zigbee coordinator and devices
├── esphome/          # ESPHome firmware configs, flashed from the server (step 25)
└── stacks/           # One folder per Docker Compose stack, managed by Dockge
```

## Stacks

| Stack | Purpose | Port(s) | Notes |
| ----- | ------- | ------- | ----- |
| `dockge` | Manages the Docker Compose stacks | 5001 (localhost only) | `dockge.local.ber.nvcode.com`, behind authentik; data in `/srv/dockge` |
| `traefik` | Reverse proxy and TLS | 80, 443 | Dashboard at `traefik.local.ber.nvcode.com`, behind authentik; certificates in `/srv/traefik/acme` |
| `beszel` | Host and container monitoring | 8090 (localhost only) | `beszel.local.ber.nvcode.com`, login via authentik (OIDC); data in `/srv/beszel` |
| `authentik` | Single sign-on and forward auth | — | `auth.local.ber.nvcode.com`; data in `/srv/authentik`. Memory-heavy: about 1–1.5 GB with PostgreSQL |
| `wud` | Reports available image updates | — | `wud.local.ber.nvcode.com`, login via authentik (OIDC); data in `/srv/wud` |
| `tailscale` | Remote access to the host and LAN | — | Host networking; subnet router for `192.168.2.0/24` and exit node; state in `/srv/tailscale` |
| `frpc` | Tunnels Home Assistant to the remote frps server | — (remote 6301) | Tunnels defined in `stacks/frpc/frpc.toml`; mTLS certificates in `/srv/frpc/certs` |
| `homeassistant` | Home Assistant, Mosquitto (MQTT), Zigbee2MQTT and Music Assistant | 8123, 8095, 8097, 3483 (host network), 1883 | `homeassistant.local.ber.nvcode.com` with Home Assistant's own login; `zigbee2mqtt.local.ber.nvcode.com` behind authentik; `musicassistant.local.ber.nvcode.com` with Music Assistant's own login (8097 is its stream server, 3483 its Squeezelite server, for the players; the Echo plays through Squeezelite on the host, [step 23](#23-play-music-assistant-on-the-amazon-echo-over-bluetooth)); music library in `/srv/music`; data in `/srv/homeassistant`. Home Assistant uses about 0.5 GB of memory. Home Assistant's tag is a monthly release, updated deliberately |
| `homarr` | Dashboard with links and widgets for the services | — | `homarr.local.ber.nvcode.com`, login via authentik (OIDC); data in `/srv/homarr`. Reads and controls Docker through the socket. Pinned to an exact release (no major-version tag), updated deliberately |
| `fmradio` | FM and DAB+ radio from an RTL-SDR dongle, as an MP3 stream for Music Assistant | 8099 (localhost only) | `http://127.0.0.1:8099/<MHz>` tunes to an FM station (mono), `/<DAB+ block>?name=<station>` to a DAB+ one. Image built from the stack's `Dockerfile` (Debian, about 680 MB, mostly welle-cli's packaged dependencies); see [step 24](#24-listen-to-fm-and-dab-radio-with-an-rtl-sdr-dongle) |
| `wyoming` | Speech to text (faster-whisper) and text to speech (Piper) for Home Assistant's Assist | 10300, 10200 (localhost only) | English; models in `/srv/wyoming`. Whisper (`distil-medium.en` model, int8) uses about 1 GB of memory. Exact releases (no version-line tags), updated deliberately; see [step 25](#25-set-up-a-voice-assistant) |

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
once from the command line; after that it shows up in its own UI. It joins the shared
`proxy` network, which Traefik and other web services use too:

```bash
docker network create proxy
sudo mkdir -p /srv/dockge/data
cd /opt/homelab-ber/stacks/dockge
docker compose up -d
```

Port 5001 only listens on localhost. Until Traefik and authentik are set up, reach Dockge
through an SSH tunnel from the Mac and create the admin account:

```bash
ssh -L 5001:localhost:5001 valentin@192.168.2.30   # then open http://localhost:5001
```

### 12. Set up Traefik with a wildcard certificate

Traefik gets a Let's Encrypt wildcard certificate for `*.local.ber.nvcode.com` using the
DNS challenge: it creates a temporary TXT record through the DreamHost API.

1. In the DreamHost panel, under *Advanced → API*, create an API key with the functions
   `dns-list_records`, `dns-add_record` and `dns-remove_record`.
2. Create the certificate directory:

   ```bash
   sudo mkdir -p /srv/traefik/acme
   ```

3. Create `stacks/traefik/.env` from [`.env.example`](stacks/traefik/.env.example) and
   fill in the API key:

   ```bash
   cd /opt/homelab-ber/stacks/traefik
   cp .env.example .env
   ```

4. Start Traefik:

   ```bash
   docker compose up -d
   docker compose logs -f    # wait for the certificate; DreamHost DNS can take minutes
   ```

The certificate is stored in `/srv/traefik/acme/acme.json` and renewed automatically.
The dashboard at `traefik.local.ber.nvcode.com` is protected by authentik, so it only becomes
reachable after step 14.

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

### 14. Put Dockge and the Traefik dashboard behind authentik

One domain-level forward-auth provider covers every `*.local.ber.nvcode.com` service; a
service is protected by adding the `authentik@docker` middleware to its Traefik router.

In authentik's admin interface (`https://auth.local.ber.nvcode.com/if/admin/`):

1. *Applications → Providers → Create → Proxy Provider*:
   - Name: `local-forward-auth`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Mode: *Forward auth (domain level)*
   - Authentication URL: `https://auth.local.ber.nvcode.com`
   - Cookie domain: `local.ber.nvcode.com`
2. *Applications → Applications → Create*:
   - Name: `Homelab`, slug: `homelab`
   - Provider: `local-forward-auth`
3. *Applications → Outposts*, edit *authentik Embedded Outpost*:
   - Add `Homelab` to the selected applications.
   - Under *Advanced settings → Configuration*, set
     `authentik_host: https://auth.local.ber.nvcode.com/`. Without it, the outpost shows
     "authentik Domain is not configured" and logins don't work.

In Dockge, turn off its own login under *Settings → Security*. Dockge's and the Traefik
dashboard's routers already use the `authentik@docker` middleware, and Dockge's port 5001
only listens on localhost.

Check in a private browser window:

- `https://dockge.local.ber.nvcode.com` and `https://traefik.local.ber.nvcode.com` redirect
  to the authentik login, and back after signing in.
- `http://192.168.2.30:5001` doesn't respond.

### 15. Set up Beszel monitoring

Beszel shows host and Docker container statistics. The hub (web interface) is served at
`beszel.local.ber.nvcode.com`; the agent runs on the host network and talks to the hub
through a Unix socket in `/srv/beszel/socket`. Login uses Beszel's own OIDC integration
with authentik, not forward auth.

1. At DreamHost, add the CNAME `beszel.local.ber.nvcode.com` → `lab.local.ber.nvcode.com`.
2. Create the data directories, and the marker folders through which the agent reports
   disk usage of the data and Docker volumes:

   ```bash
   sudo mkdir -p /srv/beszel/data /srv/beszel/socket /srv/beszel/agent
   sudo mkdir -p /data/.beszel /var/lib/docker/.beszel
   ```

3. Start only the hub, open `https://beszel.local.ber.nvcode.com` and create the first
   user. Use the same email address as your authentik user, so the OIDC login is linked to
   it later:

   ```bash
   cd /opt/homelab-ber/stacks/beszel
   cp .env.example .env
   docker compose up -d beszel
   ```

4. In Beszel, *Add System*: name `lab`, Host / IP `/beszel_socket/beszel.sock`. Copy the
   token and public key into `.env` (`TOKEN`, `KEY`), then start the agent:

   ```bash
   docker compose up -d
   ```

**authentik login (OIDC).** Beszel links the authentik login to the Beszel user with the
same email address, so the authentik user's email must match. In authentik's admin
interface:

1. One-time, shared by all OIDC apps: authentik marks email addresses as unverified, and
   Beszel ignores unverified ones (the login then fails with `{"email":"cannot be blank"}`).
   Create *Customization → Property Mappings → Create → Scope Mapping*:
   - Name: `OpenID email (verified)`, scope name: `email`
   - Expression:

     ```python
     return {
         "email": request.user.email,
         "email_verified": True,
     }
     ```

   This is safe as long as only the admin creates users and sets their email addresses.
2. *Applications → Applications → Create with provider*, choose *OAuth2/OpenID Provider*:
   - Application name: `Beszel`, slug: `beszel`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Client type: *Confidential*
   - Redirect URI (strict): `https://beszel.local.ber.nvcode.com/api/oauth2-redirect`
   - Scopes: replace the default `email` mapping with `OpenID email (verified)`
   - Note the client ID and client secret.

   The provider's *Preview* tab should show `"email_verified": true`.

In Beszel's admin panel (`https://beszel.local.ber.nvcode.com/_/`):

1. Under *Settings*, turn off *Hide collection create and edit controls*.
2. Edit the `users` collection → *Options → OAuth2*: enable it and add an
   *OpenID Connect* provider:
   - Display name: `authentik`
   - Client ID and client secret from authentik
   - Auth URL: `https://auth.local.ber.nvcode.com/application/o/authorize/`
   - Token URL: `https://auth.local.ber.nvcode.com/application/o/token/`
   - User info URL: `https://auth.local.ber.nvcode.com/application/o/userinfo/`
3. Turn *Hide collection create and edit controls* back on.
4. Log out and back in with *authentik*.

Password login is turned off in the stack (`DISABLE_PASSWORD_AUTH: "true"`), so only
authentik logins work. On a fresh setup, create the first user (step 3 above) and set up
the OIDC login with `DISABLE_PASSWORD_AUTH: "false"`, then switch it back.

### 16. Set up What's Up Docker (WUD)

WUD checks the running containers for newer images and shows them at
`wud.local.ber.nvcode.com`. It only reports updates (read-only Docker socket); updates are
applied in Dockge. Login is WUD's own OIDC integration with authentik: members of the
`authentik Admins` group become WUD admins, everyone else is rejected.

1. At DreamHost, add the CNAME `wud.local.ber.nvcode.com` → `lab.local.ber.nvcode.com`.
2. In authentik, *Applications → Applications → Create with provider*, choose
   *OAuth2/OpenID Provider*:
   - Application name: `WUD`, slug: `wud-local-ber-nvcode-com`. The slug is part of the
     discovery URL in [`stacks/wud/compose.yaml`](stacks/wud/compose.yaml); if they don't
     match, WUD shows "Error when trying to get the authentication strategies".
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Client type: *Confidential*
   - Redirect URI (strict): `https://wud.local.ber.nvcode.com/auth/oidc/authentik/cb`
   - Scopes: `openid`, `profile`, `OpenID email (verified)`, and
     `authentik default OAuth Mapping: OpenID 'groups'` if it's listed. WUD needs the
     `groups` claim for the admin role; the provider's *Preview* tab should show it.
   - Note the client ID and client secret.
3. Create the data directory and `.env`, then start it:

   ```bash
   sudo mkdir -p /srv/wud/store
   cd /opt/homelab-ber/stacks/wud
   cp .env.example .env    # fill in OIDC_CLIENT_ID and OIDC_CLIENT_SECRET
   docker compose up -d
   ```

4. Open `https://wud.local.ber.nvcode.com`; it redirects to authentik and back.

### 17. Set up Tailscale

Tailscale gives remote access to the server and the home LAN. The container uses host
networking and advertises `192.168.2.0/24` as a subnet route, so from any device on the
tailnet the `*.local.ber.nvcode.com` names (which resolve to `192.168.2.30`) work as they do
at home. The server is also an exit node, so devices can send all their internet traffic
through the home connection.

1. Enable IP forwarding on the host. Docker already turns on IPv4 forwarding, but not IPv6,
   which the exit node needs:

   ```bash
   printf 'net.ipv4.ip_forward = 1\nnet.ipv6.conf.all.forwarding = 1\n' \
     | sudo tee /etc/sysctl.d/99-tailscale.conf
   sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
   ```

2. In the [Tailscale admin console](https://login.tailscale.com/admin/settings/keys),
   generate an auth key (one-off, not ephemeral).
3. Create the state directory and `.env`, then start it:

   ```bash
   sudo mkdir -p /srv/tailscale/state
   cd /opt/homelab-ber/stacks/tailscale
   cp .env.example .env    # fill in TS_AUTHKEY
   docker compose up -d
   ```

4. In the admin console, on the `tailscale-ber` machine:
   - *Edit route settings*: approve the `192.168.2.0/24` subnet route and *Use as exit node*.
   - *Disable key expiry*, so the server doesn't drop off the tailnet after 180 days.
5. The auth key is only used for the first login; it can be removed from `.env` afterwards.

### 18. Set up frpc

frpc connects out to a remote frps server and exposes Home Assistant there on port `6301`.
The tunnels are defined in [`stacks/frpc/frpc.toml`](stacks/frpc/frpc.toml); the frps
address, its token and Home Assistant's address come from `.env`. The connection uses a
token and mutual TLS.

1. Put the client certificate, its key and the CA certificate in `/srv/frpc/certs`, as
   `ber.frpc.crt`, `ber.frpc.key` and `frp.ca.crt`:

   ```bash
   sudo mkdir -p /srv/frpc/certs
   # copy the three files in, then keep the key private
   sudo chmod 600 /srv/frpc/certs/ber.frpc.key
   ```

2. Create `.env`, then start it:

   ```bash
   cd /opt/homelab-ber/stacks/frpc
   cp .env.example .env    # fill in FRPS_ADDR, TOKEN and HA_HOST
   docker compose up -d
   docker compose logs     # should show "start proxy success" for ber-homeassistant
   ```

### 19. Set up Home Assistant, Mosquitto and Zigbee2MQTT

The `homeassistant` stack runs three services:

- **Home Assistant** on the host network, so device discovery works. It's served at
  `homeassistant.local.ber.nvcode.com` with its own login, and frpc tunnels it to the frps
  server (`HA_HOST=dockerhost` in frpc's `.env`). Traefik reaches it through
  `host.docker.internal`, which the Traefik stack maps to the host.
- **Mosquitto**, the MQTT broker, on port `1883` for the whole LAN. Anonymous access is
  off; clients log in with a user from `/srv/homeassistant/mosquitto/auth/passwd`.
- **Zigbee2MQTT** with the Zigbee coordinator, its frontend at
  `zigbee2mqtt.local.ber.nvcode.com`, behind authentik.

1. At DreamHost, add the CNAMEs `homeassistant.local.ber.nvcode.com` and
   `zigbee2mqtt.local.ber.nvcode.com` → `lab.local.ber.nvcode.com`.
2. Redeploy Traefik, so it picks up the `host.docker.internal` mapping:

   ```bash
   cd /opt/homelab-ber/stacks/traefik
   docker compose up -d
   ```

3. Plug in the coordinator and find its stable path:

   ```bash
   ls -l /dev/serial/by-id/
   ```

4. Create the data directories, `.env`, and the MQTT users. Mosquitto runs as UID 1883:

   ```bash
   sudo mkdir -p /srv/homeassistant/config /srv/homeassistant/zigbee2mqtt \
     /srv/homeassistant/mosquitto/auth /srv/homeassistant/mosquitto/data
   cd /opt/homelab-ber/stacks/homeassistant
   cp .env.example .env    # fill in ZIGBEE_DEVICE, ZIGBEE_ADAPTER and Z2M_MQTT_PASSWORD

   # Each command asks for the user's password; use Z2M_MQTT_PASSWORD for zigbee2mqtt
   docker compose run --rm mosquitto mosquitto_passwd -c /mosquitto/auth/passwd homeassistant
   docker compose run --rm mosquitto mosquitto_passwd /mosquitto/auth/passwd zigbee2mqtt
   sudo chown -R 1883:1883 /srv/homeassistant/mosquitto
   sudo chmod 600 /srv/homeassistant/mosquitto/auth/passwd
   ```

5. Start it:

   ```bash
   docker compose up -d
   ```

6. Home Assistant rejects proxied requests until it trusts the proxy, so do the first
   setup directly at `http://192.168.2.30:8123`: create the owner account, then under
   *Settings → System → Network* enable reverse proxy support and trust `172.16.0.0/12`
   (Docker's networks). Home Assistant no longer reads an `http:` block from
   `configuration.yaml`; it ignores one and shows a warning.
7. Open `https://homeassistant.local.ber.nvcode.com` and log in. Then
   *Settings → Devices & services → Add integration → MQTT*: broker `127.0.0.1`, port
   `1883`, user `homeassistant`. Zigbee devices show up there once they're paired in
   Zigbee2MQTT.
8. Set up the coordinator and pair devices as described in
   [`ZIGBEE.md`](ZIGBEE.md).
9. Helpers, automations and dashboards are described in
   [`HOMEASSISTANT.md`](HOMEASSISTANT.md).

### 20. Install BlueZ for Home Assistant's Bluetooth

Home Assistant uses the host's Bluetooth adapter through the BlueZ daemon, over D-Bus
(the stack mounts `/run/dbus`). BlueZ is only a recommended package, so the minimal
install doesn't have it, and Home Assistant logs `Failed to force stop scanner ...
'NoneType' object has no attribute 'send'`.

```bash
sudo apt install bluez
sudo systemctl enable --now bluetooth
bluetoothctl list    # should list the onboard adapter
cd /opt/homelab-ber/stacks/homeassistant
docker compose restart homeassistant
```

### 21. Start Docker only once Wi-Fi has its address

Home Assistant runs on the host network, so Docker gives it a copy of the host's
`/etc/resolv.conf` when the container starts. The installer set up Wi-Fi as
`allow-hotplug wlo1`, which `network-online.target` doesn't wait for: at boot Docker
started the containers before dhcpcd had a lease and had written the nameserver, so Home
Assistant got a `resolv.conf` without one. DNS then failed inside it (`Could not resolve
host`), e.g. Met.no's `Update of data from the website failed`. With `auto`, the boot
waits for the lease, and Docker (which starts after `network-online.target`) after it.

```bash
sudo sed -i 's/^allow-hotplug wlo1/auto wlo1/' /etc/network/interfaces
grep -n wlo1 /etc/network/interfaces    # auto wlo1
sudo reboot

# After the reboot
cd /opt/homelab-ber/stacks/homeassistant
docker compose exec homeassistant cat /etc/resolv.conf    # nameserver 192.168.2.1
docker compose exec homeassistant nslookup api.met.no
```

Without the Speedport (e.g. both coming back after a power cut), the boot now waits for
the DHCP timeout before carrying on. A container that started with the empty file is
fixed with `docker compose up -d --force-recreate <service>`.

### 22. Set up Homarr

Homarr is a dashboard for the services at `homarr.local.ber.nvcode.com`. Login is Homarr's
own OIDC integration with authentik, and only that: members of `authentik Admins` become
Homarr admins. It has the Docker socket, so it shows the containers' status and can start
and stop them.

1. At DreamHost, add the CNAME `homarr.local.ber.nvcode.com` → `lab.local.ber.nvcode.com`.
2. In authentik, *Applications → Applications → Create with provider*, choose
   *OAuth2/OpenID Provider*:
   - Application name: `Homarr`, slug: `homarr-local-ber-nvcode-com`. The slug is part of
     the issuer and logout URLs in [`stacks/homarr/compose.yaml`](stacks/homarr/compose.yaml).
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Client type: *Confidential*
   - Redirect URI (strict): `https://homarr.local.ber.nvcode.com/api/auth/callback/oidc`
   - Scopes: `openid`, `profile`, `OpenID email (verified)`, and
     `authentik default OAuth Mapping: OpenID 'groups'` if it's listed. Homarr maps the
     `groups` claim to its own groups; the provider's *Preview* tab should show it.
   - Note the client ID and client secret.
3. Create the data directory and `.env`, then start it:

   ```bash
   sudo mkdir -p /srv/homarr/appdata
   cd /opt/homelab-ber/stacks/homarr
   cp .env.example .env    # fill in OIDC_CLIENT_ID and OIDC_CLIENT_SECRET, and
   openssl rand -hex 32    # this as SECRET_ENCRYPTION_KEY
   docker compose up -d
   ```

4. Open `https://homarr.local.ber.nvcode.com` and go through the onboarding. Give
   `authentik Admins` as the admin group, so its members get admin rights when they log in
   through authentik.

### 23. Play Music Assistant on the Amazon Echo over Bluetooth

The Echo (4th generation) works as a Bluetooth speaker. Music Assistant has no Bluetooth
output of its own, so two host services connect it:

- **BlueALSA** plays Bluetooth audio (A2DP) headless, from boot, through the same BlueZ
  daemon that Home Assistant uses ([step 20](#20-install-bluez-for-home-assistants-bluetooth)).
  PulseAudio only runs inside a desktop login, so it can't do this. Its Bluetooth module
  (`pulseaudio-module-bluetooth`) must stay uninstalled: it would claim the A2DP profiles
  from BlueALSA.
- **Squeezelite** is a Music Assistant player (Squeezebox protocol) that outputs to the
  Echo through BlueALSA. Debian only ships an init script for it, so it gets its own
  systemd unit.

Both run on the host rather than in Docker, since the Bluetooth radio and audio are host
level. They need a few MB of memory.

The adapter is an Intel Wi-Fi/Bluetooth combo and the server is on Wi-Fi: streaming over
Bluetooth can cost Wi-Fi throughput. If playback drops out, that's the first suspect.

1. Install BlueALSA and Squeezelite, and stop the package's own Squeezelite instance for
   good. It runs as `lab` on the server's sound card, and `disable` alone left it running;
   masked, it can't start at all. Music Assistant would also see both instances as one
   player, since Squeezelite uses the host's MAC address as its ID by default.

   ```bash
   sudo apt install bluez-alsa-utils libasound2-plugin-bluez squeezelite alsa-utils
   sudo systemctl stop squeezelite
   sudo systemctl mask squeezelite
   dpkg -l pulseaudio-module-bluetooth    # should not be installed
   ```

2. BlueALSA may only offer the **source** role (sending audio). Debian's unit starts it
   with `-p a2dp-source -p a2dp-sink`, and with both, the Echo, which can also send audio,
   connects the wrong way round: as a source playing to the server. `OPTIONS` in
   `/etc/default/bluez-alsa` only adds to the command line, so an override replaces it:

   ```bash
   sudo mkdir -p /etc/systemd/system/bluealsa.service.d
   printf '[Service]\nExecStart=\nExecStart=/usr/bin/bluealsa -S -p a2dp-source\n' | sudo tee /etc/systemd/system/bluealsa.service.d/override.conf
   sudo systemctl daemon-reload
   sudo systemctl restart bluealsa
   bluealsa-cli status                                     # Profiles: only A2DP-source : SBC
   grep group= /usr/share/dbus-1/system.d/bluealsa.conf    # <policy group="audio">
   ```

   Its D-Bus policy lets the `audio` group use it, which Squeezelite runs in below.

3. Pair the Echo. The Echo `Echo-0CB` is `08:91:15:BB:3A:B9` (its classic Bluetooth
   address, with *Audio Sink*; it also shows up under a changing Bluetooth LE address,
   which is no use for audio).
   - Pairing mode only comes from the Alexa app: *Geräte → Echo & Alexa → the Echo →
     Bluetooth-Geräte → Neues Gerät koppeln*. *"Alexa, koppeln"* doesn't do it (in
     German, it only reconnects to devices the Echo already knows).
   - The server pairs **once** and then only connects. Pairing again while connected
     makes the Echo reject it, and the server loses the key while the Echo keeps it;
     then remove `lab` in the Alexa app and on the server, and start over.
   - Connecting right after pairing can be refused once or twice before it goes through.
   - Pair with an agent registered, in one interactive `bluetoothctl` session. Without
     one (`bluetoothctl pair` on its own), it pairs but doesn't bond: `Bonded: no`, the
     key stays in memory only, and after a reboot or Bluetooth restart the Echo can't
     be connected until it's paired again.

   Tap *Neues Gerät koppeln*, then:

   ```bash
   bluetoothctl
   # in bluetoothctl:
   agent NoInputNoOutput
   default-agent
   scan on                     # until "Echo-0CB" shows up
   pair 08:91:15:BB:3A:B9
   trust 08:91:15:BB:3A:B9
   scan off
   connect 08:91:15:BB:3A:B9   # repeat if refused; the Echo says "mit lab verbunden"
   info 08:91:15:BB:3A:B9      # Paired: yes, Bonded: yes
   quit
   ```

   `Bonded: yes` means the key is stored: `/var/lib/bluetooth/<adapter>/08:91:15:BB:3A:B9/info`
   has a `[LinkKey]` section. *lab* then shows as connected under the Echo's Bluetooth
   devices in the app. Test it:

   ```bash
   bluealsa-cli list-pcms    # .../dev_08_91_15_BB_3A_B9/a2dpsrc/sink
   speaker-test -D bluealsa:DEV=08:91:15:BB:3A:B9,PROFILE=a2dp -c 2 -t wav -l 1
   ```

   `a2dpsnk/source` instead of `a2dpsrc/sink` means it connected the wrong way round
   (step 2).

4. Squeezelite as a service. It runs as its own system user in `audio`. A `DynamicUser`
   with `SupplementaryGroups=audio` doesn't work: D-Bus looks group membership up in
   `/etc/group`, so BlueALSA refuses it (`playback open error: Connection …`).

   ```bash
   sudo useradd --system --no-create-home --shell /usr/sbin/nologin --groups audio squeezelite
   ```

   `/etc/systemd/system/squeezelite-echo.service`. The log line
   `Failed to create secure directory (//.config/pulse)` is ALSA's PulseAudio plugin
   looking for a home directory, and harmless.

   ```ini
   [Unit]
   Description=Squeezelite player for the Amazon Echo (Bluetooth)
   Wants=bluealsa.service
   After=bluealsa.service network-online.target

   [Service]
   User=squeezelite
   # -s: Music Assistant on this host; -m: its own player ID (otherwise the host's MAC);
   # -C 5: release the Echo 5 s after playback stops
   ExecStart=/usr/bin/squeezelite -n Echo -m 02:ec:00:00:00:01 -s 127.0.0.1 -C 5 -o bluealsa:DEV=08:91:15:BB:3A:B9,PROFILE=a2dp
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

5. Reconnecting: the Echo doesn't connect back to the server by itself, after a reboot or
   once it's been out of range. A timer connects it every minute if it isn't connected.
   This also means it takes the Echo back from a phone connected over Bluetooth within a
   minute. `/etc/systemd/system/echo-bluetooth-connect.service`:

   ```ini
   [Unit]
   Description=Connect the Amazon Echo over Bluetooth if it isn't
   After=bluetooth.service

   [Service]
   Type=oneshot
   # "-": a failed attempt (Echo off or out of range) isn't an error
   # The UUID (Audio Sink) makes it connect over classic Bluetooth: after a Bluetooth
   # restart, a plain connect tries Bluetooth LE and fails (le-connection-abort-by-local)
   ExecStart=-/bin/sh -c 'bluetoothctl info 08:91:15:BB:3A:B9 | grep -q "Connected: yes" || bluetoothctl connect 08:91:15:BB:3A:B9 0000110b-0000-1000-8000-00805f9b34fb'
   ```

   and `/etc/systemd/system/echo-bluetooth-connect.timer`:

   ```ini
   [Unit]
   Description=Keep the Amazon Echo connected over Bluetooth

   [Timer]
   OnBootSec=1min
   OnUnitActiveSec=1min

   [Install]
   WantedBy=timers.target
   ```

6. Start both:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now echo-bluetooth-connect.timer squeezelite-echo.service
   systemctl status squeezelite-echo
   ```

7. In Music Assistant, *Settings → Providers → Add*, add **Squeezelite** (slimproto). It
   listens on port 3483, and the player `Echo` shows up. Through the Music Assistant
   integration, Home Assistant gets it as a media player too (`media_player.echo`).

### 24. Listen to FM and DAB+ radio with an RTL-SDR dongle

The dongle is a DollarTek RTL-SDR USB 2.0 stick
([Amazon B07DJT5NHD](https://www.amazon.de/-/en/dp/B07DJT5NHD)): a Realtek RTL2832U
demodulator with a Rafael Micro R820T2 tuner. It shows up as `0bda:2838 Realtek
Semiconductor Corp. RTL2838 DVB-T`. It receives FM and DAB+, and the `fmradio` stack
turns a station into an MP3 stream until the client disconnects:

- FM: `http://127.0.0.1:8099/95.8?name=radioeins` tunes to 95.8 MHz. `rtl_fm`
  demodulates it (mono only, which makes no difference on the Echo) and `lame`
  encodes it; a few percent of one CPU core.
- DAB+: `http://127.0.0.1:8099/5C?name=Radio%20BOB!` plays the station called that
  in block 5C. DAB+ sends a whole block of stations on one frequency;
  [welle-cli](https://github.com/AlbrechtL/welle.io) receives the block and streams
  the station asked for. `name` is matched against the names the block broadcasts,
  ignoring case, spaces and punctuation. welle-cli takes about 30 % of one CPU core
  and 55 MB of memory while playing. Starting cold takes up to a minute, until the
  block lists the station; switching to another block takes 5–15 s.

`name` also goes into the stream's title tag and `icy-name` header, which Music
Assistant shows instead of the URL. Music Assistant plays it like an internet radio
station, on any of its players. There is one dongle, so only one station plays at a
time, FM or DAB+: requests for the playing station share it, and a request for
another one retunes.

Starting and stopping the tuner in quick succession hung the dongle until it was
unplugged (`usb 1-8: device descriptor read/64, error -110` in `dmesg`, and `rtl_fm`
reports `No supported devices found`). Music Assistant opens a stream several times
in a row when it starts it, so the service keeps the station playing for 15 s after
the last client is gone, and waits 2 s after releasing the dongle before starting it
again. Between DAB+ stations, welle-cli keeps running and switches blocks itself. A
retune ends the previous station's stream, and Music Assistant's player then
reconnects to it, which would retune straight back; so for 10 s after a retune the
previous station is refused (HTTP 503).

Berlin's DAB+ blocks, scanned from the server in November 2026 with the dongle's
small antenna indoors; all five came in, with a signal-to-noise ratio of 15–22 dB:

| Block | MHz | Ensemble | Stations |
|-------|-----|----------|----------|
| 5C | 178.352 | DR Deutschland | Dlf, Dlf Kultur, Dlf Nova, DRadio DokDeb, Absolut relax, ASA DE, ENERGY, ERF Plus, KLASSIK RADIO, RADIO BOB!, radio horeb, SCHLAGERPARADIES, Schwarzwaldradio, SUNSHINE LIVE |
| 5D | 180.064 | Antenne DE | 80s80s, 8090er OLDIE ANT, 90s90s, Absolut BELLA, Absolut CLASSICS, Absolut GERMANY, Absolut HOT, Absolut TOP 2000, AIDAradio, BALLERMANN RADIO, Beats Radio, Brillux Radio, NOSTALGIE, ROCK ANTENNE, RTL RADIO, TOGGO Radio |
| 7B | 190.640 | Berlin/BRBG 7B | \*STAR\*SAT\*RADIO\*, 106.8 pure fm, 60er70er GOLD, ByteFM, DISCOFOX ANTENNE, ELLA, FG CHIC.de, JAM FM, JazzRadio Berlin, MEGARADIOmix.de, Metropol FM, NIUS - Das Radio, RADIO ORIENT, RADIO TEDDY, Radio Holiday, Radio Paradiso |
| 7D | 194.064 | rbb Berlin K7D | Antenne P, BR Heimat, BR Klassik, COSMO, FR-BB & 24/3, Fritz, radio1, radio3 vom rbb, rbb 88.8, rbb24 Inforadio, WDR Maus |
| 12D | 229.072 | Berlin/BRBG K12D | 104.6RTL, 105'5 SPREERADIO, 98.8 KISS FM, ALEX RADIO, BB RADIO, bigFM, BOLLERWAGEN, BRF 91.4, ENERGY BERLIN, POWER RADIO, RADIO GINSENG, Radio BHeins, Radio Cottbus, Radio Paloma, RADIO POTSDAM, STAR FM MAX ROCK |

1. Keep the kernel's DVB-T TV driver off the dongle. It would claim it, and `rtl_fm`
   then fails with `usb_claim_interface error -6`:

   ```bash
   echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf
   # If the dongle is already plugged in (or unplug and replug it)
   sudo modprobe -r rtl2832_sdr dvb_usb_rtl28xxu
   lsmod | grep dvb_usb                 # nothing; leftovers like rtl2832 or dvb_core are unused
   ```

2. Deploy the `fmradio` stack in Dockge. Dockge builds the image from the stack's
   `Dockerfile`; to pick up changes to it or `fmradio.py`, rebuild with
   `docker compose up -d --build` in `/opt/homelab-ber/stacks/fmradio`. Test it with a
   station:

   ```bash
   curl -s -m 10 http://127.0.0.1:8099/95.8 -o /tmp/test.mp3; ls -l /tmp/test.mp3   # ~150 KB
   curl -s -m 60 'http://127.0.0.1:8099/7D?name=Fritz' -o /tmp/test.mp3; ls -l /tmp/test.mp3   # some 100 KB
   ```

   Distorted FM, as if not quite tuned in: the tuner is overloaded. Automatic gain turns it
   up too far for strong transmitters; `GAIN` in `compose.yaml` fixes it (20 dB here,
   picked by ear from test recordings at 10, 20, 30 dB and auto). Silence or hiss: the
   antenna. The dongle's clock is 15–40 ppm off (`rtl_test -p`), which is 2–4 kHz at
   100 MHz and doesn't matter for FM; `PPM` would correct it. DAB+ uses automatic
   gain and corrects the clock itself. A DAB+ station that never starts (the log says
   `<name> not found in block <block>`): its name differs from what the block
   broadcasts, or the block doesn't come in. DAB+ is at 175–230 MHz, so a telescopic
   antenna works best at about 35–40 cm there, against about 75 cm for FM.

   To see what a block broadcasts, run welle-cli's own web interface with the stack
   stopped (it needs the dongle), and open it through an SSH tunnel
   (`ssh -L 7979:127.0.0.1:7979 …`) at `http://localhost:7979`:

   ```bash
   docker compose stop
   docker run --rm -p 127.0.0.1:7979:7979 -v /dev/bus/usb:/dev/bus/usb \
     --device-cgroup-rule='c 189:* rmw' fmradio:local welle-cli -c 7D -w 7979
   # Ctrl-C, then: docker compose start
   ```

3. Optionally, add stations to Music Assistant's library, to pick them in its own app:
   under *Library → Radio*, add an item from a URL, `http://127.0.0.1:8099/<MHz>` or
   `http://127.0.0.1:8099/<block>?name=<station>`, and name it. Home Assistant doesn't need them (see `HOMEASSISTANT.md`).

### 25. Set up a voice assistant

A Waveshare ESP32-S3-AUDIO-Board (four microphones, a speaker, seven LEDs, three keys)
works as a Home Assistant voice satellite. It runs ESPHome: it listens for the wake word
*"Okay Nabu"* itself, then streams the request to Home Assistant, which turns it into
text, acts on it, and sends the spoken reply back. Speech runs locally, in the
`wyoming` stack. The board is on Wi-Fi; USB is only for power and the first flash.

It came with the XiaoZhi firmware, a Chinese AI assistant that talks to its own cloud.
Flashing ESPHome replaces it.

1. Deploy the `wyoming` stack in Dockge. On first start, whisper downloads its model and
   Piper its voice into `/srv/wyoming`; the logs show when they're ready.

2. Secrets for the board, in the repo checkout on the server (git-ignored):

   ```bash
   cd /opt/homelab-ber/esphome
   cp secrets.yaml.example secrets.yaml
   openssl rand -base64 32    # → api_encryption_key
   nano secrets.yaml          # Wi-Fi name and password, the key, a fallback hotspot password
   ```

3. Flash it over USB from the server with ESPHome's image, without an ESPHome stack
   (`esphome/voice-satellite.yaml`). The first build downloads the toolchain and takes
   10–15 minutes; it's kept in `/srv/esphome/cache`, and the build output in
   `esphome/.esphome` (git-ignored):

   ```bash
   cd /opt/homelab-ber/esphome
   docker run --rm -v "$PWD":/config -v /srv/esphome/cache:/cache \
     --device /dev/ttyACM0 esphome/esphome:2026.10 \
     run voice-satellite.yaml --device /dev/ttyACM0
   ```

   It then shows the board's log; it should connect to Wi-Fi. `Ctrl+C` ends the log.
   Later changes can go over Wi-Fi: the same command without `--device`.

4. Home Assistant finds it: *Settings → Devices & services*, *ESPHome* under
   *Discovered*. Adding it asks for `api_encryption_key`. The Assist pipeline it uses
   is in `HOMEASSISTANT.md`.

