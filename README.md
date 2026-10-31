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

- **`/`** holds the OS. The Dockge stacks directory (`/opt/stacks`) lives here too.
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
- DNS, remote access: _TBD_

## Container platform

- All services run in Docker containers.
- Docker Compose stacks are managed with [Dockge](https://github.com/louislam/dockge).
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
| _none yet_ |    |         |       |

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

### 4. Move `/home` and `/srv` onto the data volume

The installer can't create bind mounts, so this is done after the first boot. Switch to a
text console (Ctrl+Alt+F2) and log in there **without** logging into Xfce, so nothing in
the home directory is in use.

```bash
# Copy the home directory created by the installer onto the data volume
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

After the reboot, log into Xfce and check the home directory is intact, then remove the
fallback copy:

```bash
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

Install only the core of Xfce, a terminal and a display manager:

```bash
sudo apt install xfce4 xfce4-terminal lightdm
sudo reboot
```
