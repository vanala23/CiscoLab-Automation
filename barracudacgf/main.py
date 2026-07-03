import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from proxmox import clone_vm, set_vlan_tag, start_vm, wait_for_vm, vm_exists, delete_vm
from cgf import wait_for_cgf, configure_cgf
from config import VLANS, CGF_DHCP_SERVICE, CGF_DHCP_SUBNET, VLAN_IP_MAP
from utils import print_ok, print_info, print_err, print_skip, print_header

MAX_RETRIES = 3


def deploy(vlan_id: int) -> None:
    """Deploy a Barracuda CGF VM for the specified VLAN."""
    print_header(f"Deploying CGF{vlan_id} (VLAN {vlan_id})")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if vm_exists(vlan_id):
                print_info("VM already exists, deleting...")
                delete_vm(vlan_id)
            clone_vm(vlan_id)
            set_vlan_tag(vlan_id)
            start_vm(vlan_id)
            wait_for_vm(vlan_id)
            wait_for_cgf()
            configure_cgf(vlan_id, service=CGF_DHCP_SERVICE, subnet_name=CGF_DHCP_SUBNET)
            print_ok(f"CGF{vlan_id} deployed successfully -> {VLAN_IP_MAP[vlan_id]}")
            return
        except Exception as e:
            print_err(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            try:
                if vm_exists(vlan_id):
                    delete_vm(vlan_id)
            except Exception as ce:
                print_err(f"Cleanup failed: {ce}")
            if attempt == MAX_RETRIES:
                print_err(f"CGF{vlan_id} skipped after {MAX_RETRIES} attempts")
            else:
                print_info("Retrying...")


def delete_all() -> None:
    """Delete all CGF VMs after user confirmation."""
    print_header("Delete All CGF VMs")
    confirm = input("Are you sure? All CGF VMs will be deleted [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled")
        return
    for vlan in VLANS:
        if vm_exists(vlan):
            delete_vm(vlan)
        else:
            print_skip(f"CGF{vlan} does not exist")
    print_ok("All VMs deleted")


def main() -> None:
    """Display menu and handle user selection."""
    print_header("Barracuda CGF Automation")
    print("\nAvailable VLANs:")
    for i, vlan in enumerate(VLANS):
        print(f"  [{i}] VLAN {vlan}")
    print("\n  [a] Deploy all")
    print("  [d] Delete all VMs")
    choice = input("\nSelect: ").strip()
    if choice == "a":
        for vlan in VLANS:
            deploy(vlan)
    elif choice == "d":
        delete_all()

    elif choice.isdigit() and int(choice) < len(VLANS):
        deploy(VLANS[int(choice)])
    else:
        print("Invalid selection")


if __name__ == "__main__":
    main()



