from dotenv import load_dotenv
import os

load_dotenv("../.env")
load_dotenv(".env")

PROXMOX_HOST = os.getenv("PROXMOX_HOST")
PROXMOX_TOKEN = os.getenv("PROXMOX_TOKEN")
PROXMOX_NODE = os.getenv("PROXMOX_NODE")
TEMPLATE_ID = int(os.getenv("TEMPLATE_ID"))
CGF_MGMT_IP = os.getenv("CGF_MGMT_IP")
CGF_TOKEN = os.getenv("CGF_TOKEN")
CGF_DHCP_SERVICE = os.getenv("CGF_DHCP_SERVICE")
CGF_DHCP_SUBNET = os.getenv("CGF_DHCP_SUBNET")

VLANS = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53, 61, 62, 63, 71]

VLAN_IP_MAP = {
    11: "10.132.1.111", 12: "10.132.1.112", 13: "10.132.1.113",
    21: "10.132.1.121", 22: "10.132.1.122", 23: "10.132.1.123",
    31: "10.132.1.131", 32: "10.132.1.132", 33: "10.132.1.133",
    41: "10.132.1.141", 42: "10.132.1.142", 43: "10.132.1.143",
    51: "10.132.1.151", 52: "10.132.1.152", 53: "10.132.1.153",
    61: "10.132.1.161", 62: "10.132.1.162", 63: "10.132.1.163",
    71: "10.132.1.171",
}

def vmid(vlan_id: int) -> int:
    """Generate Proxmox VM ID from VLAN ID."""
    return int(f"10{vlan_id}")

def vm_name(vlan_id: int) -> str:
    """Generate VM name from VLAN ID."""
    return f"CGF{vlan_id}"
