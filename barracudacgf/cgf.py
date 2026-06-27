import requests
import urllib3
import time
from config import CGF_MGMT_IP, CGF_TOKEN, VLAN_IP_MAP
from utils import print_ok, print_info, print_err

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {"X-API-Token": CGF_TOKEN, "Content-Type": "application/json"}


def _base(ip: str = None) -> str:
    return f"https://{ip or CGF_MGMT_IP}:8443/rest/config/v1"

def _control(ip: str = None) -> str:
    return f"https://{ip or CGF_MGMT_IP}:8443/rest/control/v1"


def wait_for_cgf(ip: str = None, timeout: int = 600) -> None:
    """Wait for the CGF REST API to become available."""
    print_info("Waiting for CGF API...")
    start = time.time()
    for attempt in range(timeout):
        try:
            r = requests.get(
                f"{_base(ip)}/box/network/management",
                headers=HEADERS, verify=False, timeout=3
            )
            if r.status_code in [200, 401]:
                print_ok(f"CGF API reachable ({time.time()-start:.0f}s), waiting 90s for full boot...")
                time.sleep(90)
                print_ok("Ready")
                return
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        if attempt % 30 == 0 and attempt > 0:
            print_info(f"Still waiting... ({time.time()-start:.0f}s)")
        time.sleep(1)
    raise TimeoutError("CGF API unreachable")


def wait_for_ip_change(new_ip: str, timeout: int = 120) -> None:
    """Wait for CGF to become reachable at its new IP address."""
    print_info(f"Waiting for CGF at {new_ip}...")
    for _ in range(timeout):
        try:
            r = requests.get(
                f"{_base(new_ip)}/box/network/management",
                headers=HEADERS, verify=False, timeout=3
            )
            if r.status_code in [200, 401]:
                print_ok(f"CGF reachable at {new_ip}")
                return
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        time.sleep(1)
    raise TimeoutError(f"CGF not reachable at {new_ip}")


def begin_session(ip: str = None) -> str:
    """Start a new configuration session and return the session token."""
    r = requests.post(f"{_base(ip)}/begin", headers=HEADERS, verify=False, timeout=5)
    r.raise_for_status()
    return r.json().get("token")


def commit_session(session_token: str, ip: str = None) -> None:
    """Commit configuration changes."""
    try:
        r = requests.post(
            f"{_base(ip)}/commit", headers=HEADERS,
            params={"token": session_token}, verify=False, timeout=5
        )
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        pass


def activate_network(ip: str = None) -> None:
    """Trigger a soft network activation."""
    try:
        requests.post(
            f"{_control(ip)}/box/net/activate/soft",
            headers=HEADERS, verify=False, timeout=5
        )
    except requests.exceptions.ConnectionError:
        pass
    print_ok("Network activation triggered")


def set_management_ip(vlan_id: int, session_token: str, ip: str = None) -> None:
    """Set the management IP address for the given VLAN."""
    new_ip = VLAN_IP_MAP[vlan_id]
    print_info(f"Setting management IP to {new_ip}")
    r = requests.patch(
        f"{_base(ip)}/box/network/management",
        headers=HEADERS,
        params={"token": session_token},
        json={
            "address": {"ip": new_ip, "mask": 22},
            "sharedIps": {
                "remove": [CGF_MGMT_IP],
                "add": [{"ip": new_ip, "alias": "none", "pingable": True}]
            }
        },
        verify=False, timeout=5
    )
    r.raise_for_status()
    print_ok("Management IP set")


def set_dhcp_subnet(vlan_id: int, service: str, subnet_name: str, session_token: str, ip: str = None) -> None:
    """Configure the DHCP subnet range for the given VLAN."""
    print_info(f"Setting DHCP range for VLAN {vlan_id}")
    r = requests.put(
        f"{_base(ip)}/service-container/{service}/dhcp/subnets/{subnet_name}",
        headers=HEADERS,
        params={"token": session_token},
        json={
            "properties": {
                "ranges": [{"startIp": f"192.168.{vlan_id}.10", "endIp": f"192.168.{vlan_id}.100"}],
                "routers": [f"192.168.{vlan_id}.1"],
                "dnsServers": [f"192.168.{vlan_id}.1"],
                "ntpServers": [],
                "subnet": f"192.168.{vlan_id}.0/24",
                "interface": "eth1",
                "vendorId": "",
                "vendorIdConversion": "hex"
            }
        },
        verify=False, timeout=5
    )
    r.raise_for_status()
    print_ok("DHCP range set")


def configure_cgf(vlan_id: int, service: str = "DHCP", subnet_name: str = "LAN") -> None:
    """Run full CGF configuration: management IP + network activation + DHCP."""
    new_ip = VLAN_IP_MAP[vlan_id]

    # Step 1: Set management IP on original IP
    token = begin_session()
    try:
        set_management_ip(vlan_id, token)
        commit_session(token)
        activate_network()
    except Exception as e:
        print_err(f"Failed to set management IP: {e} — rolling back")
        try:
            requests.post(
                f"{_base()}/rollback", headers=HEADERS,
                params={"token": token}, verify=False, timeout=5
            )
        except requests.exceptions.ConnectionError:
            pass
        raise

    # Step 2: Wait for CGF on new IP
    time.sleep(5)
    wait_for_ip_change(new_ip)

    # Step 3: Configure DHCP on new IP
    token = begin_session(ip=new_ip)
    try:
        set_dhcp_subnet(vlan_id, service, subnet_name, token, ip=new_ip)
        commit_session(token, ip=new_ip)
        print_ok(f"CGF configured -> {new_ip}")
    except Exception as e:
        print_err(f"Failed to set DHCP: {e} — rolling back")
        try:
            requests.post(
                f"{_base(new_ip)}/rollback", headers=HEADERS,
                params={"token": token}, verify=False, timeout=5
            )
        except requests.exceptions.ConnectionError:
            pass
        raise
