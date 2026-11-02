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
├── .gitignore    # Keeps real .env files out of git
├── README.md     # Server configuration (this file)
├── AGENTS.md     # Instructions for AI coding agents working in this repo
└── stacks/       # One folder per Docker Compose stack, managed by Dockge
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
| `homeassistant` | Home Assistant, Mosquitto (MQTT) and Zigbee2MQTT | 8123 (host network), 1883 | `homeassistant.local.ber.nvcode.com` with Home Assistant's own login; `zigbee2mqtt.local.ber.nvcode.com` behind authentik; data in `/srv/homeassistant`. Home Assistant uses about 0.5 GB of memory. Tag is a monthly release, updated deliberately |

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
   [`stacks/homeassistant/ZIGBEE.md`](stacks/homeassistant/ZIGBEE.md).
9. Helpers, automations and dashboards are described in
   [`stacks/homeassistant/HOMEASSISTANT.md`](stacks/homeassistant/HOMEASSISTANT.md).

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
