# CiscoLab-Automation

Automated deployment and configuration of virtualized network infrastructure on Proxmox. This project is developed as part of the HTL Kaindorf school lab environment and aims to fully automate the setup of firewall VMs per VLAN — replacing a previously manual, time-consuming process.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Global Configuration](#global-configuration)
- [Modules](#modules)
  - [Barracuda CloudGen Firewall](#barracuda-cloudgen-firewall)
- [Running the Project](#running-the-project)
- [Extending the Project](#extending-the-project)

---

## Overview

CiscoLab-Automation is a modular Python project that automates the deployment of virtual machines on a Proxmox hypervisor and configures them via REST APIs. Each module targets a specific product or use case (e.g. Barracuda CGF, Windows Server).

The root `main.py` acts as a launcher that lets you pick which module to run.

---

## Project Structure

```
CiscoLab-Automation/
├── main.py                  # Root launcher — select which module to run
├── .env                     # Global secrets (Proxmox credentials)
├── .env.example             # Template for global secrets
├── .gitignore
├── README.md
└── barracudacgf/
    ├── main.py              # Barracuda CGF module entry point
    ├── config.py            # Loads env vars, defines VLAN/IP mappings
    ├── proxmox.py           # Proxmox API functions (clone, start, delete...)
    ├── cgf.py               # Barracuda CGF REST API functions
    ├── utils.py             # Shared print helpers
    ├── .env                 # CGF-specific secrets
    └── .env.example         # Template for CGF secrets
```

---

## Requirements

### System

- **OS:** Linux (tested on Arch Linux / CachyOS)
- **Python:** 3.10+
- **Packages:**

```bash
pip install requests python-dotenv
```

### Infrastructure

- A running **Proxmox VE** instance (tested on 9.x)
- A **Barracuda CloudGen Firewall** VM template on Proxmox (VMID `1000`)
- Network bridges configured:
  - `vmbr0` — Management network (`10.132.1.0/22`)
  - `vmbr1` — VLAN-aware client bridge

---

## Global Configuration

Create a `.env` file in the root directory based on `.env.example`:

```env
PROXMOX_HOST=https://<PROXMOX-IP>:8006/api2/json
PROXMOX_TOKEN=PVEAPIToken=root@pam!automation=<YOUR-SECRET>
PROXMOX_NODE=pve
```

### Creating a Proxmox API Token

1. Open the Proxmox Web UI
2. Go to `Datacenter > Permissions > API Tokens > Add`
3. User: `root@pam`, Token ID: `automation`
4. **Disable Privilege Separation**
5. Copy the token secret — it is only shown once
6. Go to `Datacenter > Permissions > Add > API Token Permission`
   - Path: `/`, Role: `Administrator`, Propagate: ✓

---

## Modules

### Barracuda CloudGen Firewall

This module automates the full deployment lifecycle of a Barracuda CGF VM for each VLAN in the school lab. It clones a pre-configured template, sets the correct VLAN tag, starts the VM, waits for the REST API to become available, and then configures the management IP, LAN address, DHCP range, and VLAN interface — all via the Barracuda REST API.

---

#### How It Works

The deploy flow for each VLAN:

```
1. Check if VM already exists → delete if so
2. Clone template (VMID 1000) → new VMID: 10{VLAN_ID}, name: CGF{VLAN_ID}
3. Set VLAN tag on net1 (vmbr1)
4. Start VM and wait until running
5. Wait for CGF REST API to become available (up to 10 min)
6. Wait additional 90s for full CGF initialization
7. Set management IP (10.132.1.1{VLAN_ID}) via REST API
8. Commit + soft network activation
9. Wait for CGF to come back up on new IP
10. Configure VLAN interface on p2 (eth1)
11. Set additional LAN address (192.168.{VLAN_ID}.1)
12. Set DHCP subnet range (192.168.{VLAN_ID}.10 - .100)
13. Commit changes
```

On failure at any step, the VM is automatically deleted and the process retries up to 3 times. After 3 failed attempts, the VLAN is skipped and the next one continues.

---

#### Network Layout

| VLAN | Management IP   | LAN Gateway       | DHCP Range                    | VMID |
|------|----------------|-------------------|-------------------------------|------|
| 11   | 10.132.1.111   | 192.168.11.1      | 192.168.11.10 – 192.168.11.100 | 1011 |
| 12   | 10.132.1.112   | 192.168.12.1      | 192.168.12.10 – 192.168.12.100 | 1012 |
| 13   | 10.132.1.113   | 192.168.13.1      | 192.168.13.10 – 192.168.13.100 | 1013 |
| 21   | 10.132.1.121   | 192.168.21.1      | 192.168.21.10 – 192.168.21.100 | 1021 |
| ...  | ...            | ...               | ...                           | ...  |
| 71   | 10.132.1.171   | 192.168.71.1      | 192.168.71.10 – 192.168.71.100 | 1071 |

VM naming: `CGF{VLAN_ID}` (e.g. `CGF11`, `CGF21`)

---

#### Template Requirements

The Barracuda CGF template (VMID `1000`) must be pre-configured with:

- **Management IP:** `10.132.1.200/22` on `eth0` / `net0` (connected to `vmbr0`)
- **net1** connected to `vmbr1` (VLAN tag is set per-clone by the script)
- **REST API Service** enabled on HTTPS port `8443` with "Bind to Management IPs" active
- A valid **HTTPS certificate** (self-signed is fine)
- A **root-level API token** created and saved

##### Setting up the REST API on the template

1. Open Firewall Admin GUI at `https://10.132.1.200`
2. Go to `CONFIGURATION > Configuration Tree > Box > Infrastructure Services > REST API Service`
3. Lock → Enable HTTPS, Port `8443`, enable "Bind to Management IPs"
4. Create a certificate: New Key → Ex/Import → self-signed, CN: `10.132.1.200`
5. Go to `Box > Administrators` → add admin `root` with Manager role
6. Back in REST API Service → Access Tokens → add token for `root`
7. Copy the token → paste into `barracudacgf/.env` as `CGF_TOKEN`
8. Send Changes → Activate
9. In Proxmox: right-click VM → **Convert to Template**

---

#### Barracuda CGF Configuration

Create `barracudacgf/.env` based on `barracudacgf/.env.example`:

```env
TEMPLATE_ID=1000
CGF_MGMT_IP=10.132.1.200
CGF_TOKEN=<YOUR-CGF-API-TOKEN>
CGF_DHCP_SERVICE=DHCP
CGF_DHCP_SUBNET=LAN
```

---

#### Running the Barracuda CGF Module

From the project root:

```bash
python3 main.py
```

Select `[1] Barracuda CGF`, then choose an option:

```
==================================================
  Barracuda CGF Automation
==================================================

Available VLANs:
  [0] VLAN 11
  [1] VLAN 12
  ...
  [18] VLAN 71

  [a] Deploy all
  [d] Delete all VMs

Select:
```

- Enter a number to deploy a single VLAN
- Enter `a` to deploy all VLANs sequentially
- Enter `d` to delete all CGF VMs (with confirmation prompt)

You can also run the module directly:

```bash
cd barracudacgf
python3 main.py
```

---

#### Key Technical Details

**API Base Paths:**
- Configuration: `https://<IP>:8443/rest/config/v1/`
- Control (activation): `https://<IP>:8443/rest/control/v1/`
- DHCP operative data: `https://<IP>:8443/rest/dhcp/v1/`

**Authentication:** `X-API-Token` header

**Session flow:** Every configuration change requires:
1. `POST /rest/config/v1/begin` → returns session token
2. API calls with `?token=<session_token>`
3. `POST /rest/config/v1/commit?token=<session_token>`
4. `POST /rest/control/v1/box/net/activate/soft` (for network changes)

**Connection resets** after commit and activate are expected — the CGF drops the connection when applying network changes.

**Interface naming in CGF:**
- `p1` = `eth0` (Management, connected to `vmbr0`)
- `p2` = `eth1` (LAN/VLAN, connected to `vmbr1`)

---

## Running the Project

```bash
# Clone the repo
git clone https://github.com/<your-repo>/CiscoLab-Automation.git
cd CiscoLab-Automation

# Install dependencies (Arch Linux)
sudo pacman -S python python-requests python-dotenv

# Set up environment files
cp .env.example .env
cp barracudacgf/.env.example barracudacgf/.env
# → Edit both .env files with your credentials

# Run
python3 main.py
```

---

## Extending the Project

To add a new module (e.g. Windows Server):

1. Create a new folder: `windowsserver/`
2. Add `main.py`, `config.py`, etc. following the same structure
3. Register the module in the root `main.py`:

```python
MODULES = {
    "1": ("Barracuda CGF", "barracudacgf"),
    "2": ("Windows Server", "windowsserver"),  # add this
}
```

Each module is fully self-contained and only shares the global `.env` for Proxmox credentials.

---

## Notes

- `.env` files are excluded from Git via `.gitignore` — never commit secrets
- The project was developed and tested in the HTL Kaindorf lab environment
