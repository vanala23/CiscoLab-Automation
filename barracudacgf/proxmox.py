import requests
import urllib3
import time
from config import PROXMOX_HOST, PROXMOX_TOKEN, PROXMOX_NODE, vmid, vm_name
from utils import print_ok, print_info, print_err

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = PROXMOX_HOST
HEADERS = {"Authorization": PROXMOX_TOKEN}


def _task_wait(upid: str, timeout: int = 300) -> None:
    """Wait for a Proxmox task to complete."""
    for _ in range(timeout):
        try:
            r = requests.get(
                f"{BASE}/nodes/{PROXMOX_NODE}/tasks/{upid}/status",
                headers=HEADERS, verify=False, timeout=5
            )
            r.raise_for_status()
            data = r.json()["data"]
            if data.get("status") == "stopped":
                if data.get("exitstatus") == "OK":
                    return
                else:
                    raise Exception(f"Task failed: {data.get('exitstatus')}")
        except Exception as e:
            if "Task failed" in str(e):
                raise
        time.sleep(1)
    raise TimeoutError("Task timed out")


def clone_vm(vlan_id: int) -> None:
    """Clone the template VM for the specified VLAN."""
    print_info(f"Cloning template -> VMID {vmid(vlan_id)} ({vm_name(vlan_id)})")
    r = requests.post(
        f"{BASE}/nodes/{PROXMOX_NODE}/qemu/1000/clone",
        headers=HEADERS,
        json={"newid": vmid(vlan_id), "name": vm_name(vlan_id), "full": True, "target": PROXMOX_NODE},
        verify=False, timeout=10
    )
    r.raise_for_status()
    _task_wait(r.json()["data"])
    print_ok("Cloned successfully")


def set_vlan_tag(vlan_id: int) -> None:
    """Set VLAN tag on net1/vmbr1, keeping net0 on vmbr0."""
    print_info(f"Setting VLAN tag {vlan_id} on net1/vmbr1")
    r = requests.get(
        f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/config",
        headers=HEADERS, verify=False, timeout=5
    )
    r.raise_for_status()
    net1 = r.json()["data"].get("net1", "")
    new_net1 = (
        f"{net1.split(',')[0]},bridge=vmbr1,tag={vlan_id}"
        if net1.startswith("virtio")
        else f"virtio,bridge=vmbr1,tag={vlan_id}"
    )
    r = requests.put(
        f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/config",
        headers=HEADERS, json={"net1": new_net1}, verify=False, timeout=5
    )
    r.raise_for_status()
    print_ok(f"VLAN tag {vlan_id} set on net1")


def start_vm(vlan_id: int) -> None:
    """Start the CGF virtual machine."""
    print_info(f"Starting {vm_name(vlan_id)}")
    r = requests.post(
        f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/status/start",
        headers=HEADERS, verify=False, timeout=10
    )
    r.raise_for_status()
    _task_wait(r.json()["data"])
    print_ok("VM started")


def wait_for_vm(vlan_id: int, timeout: int = 120) -> None:
    """Wait for VM to enter running state."""
    print_info("Waiting for VM to be running...")
    for _ in range(timeout):
        try:
            r = requests.get(
                f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/status/current",
                headers=HEADERS, verify=False, timeout=5
            )
            if r.json()["data"]["status"] == "running":
                print_ok("VM is running")
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("VM did not start in time")


def vm_exists(vlan_id: int) -> bool:
    """Check if a VM exists for the given VLAN."""
    try:
        r = requests.get(
            f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/status/current",
            headers=HEADERS, verify=False, timeout=5
        )
        return r.status_code == 200
    except Exception:
        return False


def delete_vm(vlan_id: int) -> None:
    """Stop and delete the CGF virtual machine."""
    print_info(f"Deleting {vm_name(vlan_id)}")
    try:
        r = requests.get(
            f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/status/current",
            headers=HEADERS, verify=False, timeout=5
        )
        if r.json()["data"]["status"] == "running":
            stop = requests.post(
                f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}/status/stop",
                headers=HEADERS, verify=False, timeout=10
            )
            stop.raise_for_status()
            _task_wait(stop.json()["data"], timeout=60)
    except Exception:
        pass
    r = requests.delete(
        f"{BASE}/nodes/{PROXMOX_NODE}/qemu/{vmid(vlan_id)}",
        headers=HEADERS, verify=False, timeout=10
    )
    r.raise_for_status()
    _task_wait(r.json()["data"], timeout=60)
    print_ok("VM deleted")
