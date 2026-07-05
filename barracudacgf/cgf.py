import requests
import urllib3
import time

from config import CGF_MGMT_IP, CGF_TOKEN, VLAN_IP_MAP
from utils import print_ok, print_info, print_err

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================
# GLOBAL STATE
# =========================================================

CURRENT_IP = None

HEADERS = {
    "X-API-Token": CGF_TOKEN,
    "Content-Type": "application/json"
}


# =========================================================
# IP RESOLUTION (CRITICAL FIX)
# =========================================================

def resolve_ip(ip=None):
    """
    ALWAYS use CURRENT_IP if available.
    This prevents fallback to stale bootstrap IPs like 10.132.1.200.
    """
    global CURRENT_IP

    if ip:
        return ip
    if CURRENT_IP:
        return CURRENT_IP
    return CGF_MGMT_IP


def base(ip=None):
    ip = resolve_ip(ip)
    return f"https://{ip}:8443/rest/config/v1"


def ctrl(ip=None):
    ip = resolve_ip(ip)
    return f"https://{ip}:8443/rest/control/v1"


# =========================================================
# SAFE REQUEST WRAPPER
# =========================================================

def req(method, url, **kwargs):
    r = requests.request(method, url, **kwargs)

    if r.status_code >= 400:
        print_err(r.text)

    r.raise_for_status()
    return r


# =========================================================
# SESSION
# =========================================================

def begin(ip=None):
    r = req(
        "POST",
        f"{base(ip)}/begin",
        headers=HEADERS,
        verify=False,
        timeout=10
    )
    return r.json()["token"]


def commit(token, ip=None):
    try:
        req(
            "POST",
            f"{base(ip)}/commit",
            headers=HEADERS,
            params={"token": token},
            verify=False,
            timeout=10
        )
    except:
        pass


def rollback(token, ip=None):
    try:
        requests.post(
            f"{base(ip)}/rollback",
            headers=HEADERS,
            params={"token": token},
            verify=False,
            timeout=10
        )
    except:
        pass


# =========================================================
# WAITING (FIXED MAIN COMPATIBILITY)
# =========================================================

def wait_for_api():
    """
    MAIN COMPATIBLE (NO ARGUMENTS!)
    Uses CURRENT_IP internally.
    """
    print_info("Waiting for CGF API...")

    ip = resolve_ip()

    for _ in range(180):
        try:
            r = requests.get(
                f"https://{ip}:8443/rest/config/v1/box/network/management",
                headers=HEADERS,
                verify=False,
                timeout=3
            )
            if r.status_code in (200, 401):
                print_ok("CGF reachable")
                return
        except:
            pass

        time.sleep(2)

    raise TimeoutError("CGF API not reachable")


def wait_for_ip(ip):
    """
    Wait until NEW management IP is actually active.
    """
    global CURRENT_IP

    print_info(f"Waiting for CGF at {ip}...")

    for _ in range(120):
        try:
            r = requests.get(
                f"https://{ip}:8443/rest/config/v1/box/network/management",
                headers=HEADERS,
                verify=False,
                timeout=3
            )
            if r.status_code in (200, 401):
                CURRENT_IP = ip
                print_ok(f"CGF reachable at {ip}")
                return
        except:
            pass

        time.sleep(2)

    raise TimeoutError(f"CGF not reachable at {ip}")


# =========================================================
# STEP 1: MANAGEMENT IP
# =========================================================

def set_management(vlan_id, token, ip=None):
    global CURRENT_IP

    new_ip = VLAN_IP_MAP[vlan_id]
    print_info(f"Setting management IP -> {new_ip}")

    req(
        "PATCH",
        f"{base(ip)}/box/network/management",
        headers=HEADERS,
        params={"token": token},
        json={
            "address": {
                "ip": new_ip,
                "mask": 22
            }
        },
        verify=False,
        timeout=10
    )

    CURRENT_IP = new_ip
    print_ok("Management IP updated")


# =========================================================
# STEP 2: LAN (IDEMPOTENT)
# =========================================================

def set_lan(vlan_id, token, ip=None):
    lan_ip = f"192.168.{vlan_id}.1"

    print_info(f"Setting LAN -> {lan_ip}")

    req(
        "PUT",
        f"{base(ip)}/box/network/additional-address/v4/LAN",
        headers=HEADERS,
        params={"token": token},
        json={
            "name": "LAN",
            "properties": {
                "ipAddress": lan_ip,
                "mask": "255.255.255.0",
                "interface": "p1",
                "respondsToPing": True,
                "isManagementIp": False,
                "sharedIps": [
                    {
                        "ipAddress": lan_ip,
                        "alias": "none",
                        "respondsToPing": True
                    }
                ],
                "directInternetAccess": False
            }
        },
        verify=False,
        timeout=10
    )

    print_ok("LAN configured")


# =========================================================
# STEP 3: DHCP MODE
# =========================================================

def set_dhcp_mode(token, ip=None):
    print_info("Setting DHCP mode -> sharedIp")

    req(
        "PATCH",
        f"{base(ip)}/box/network/dhcp/v4",
        headers=HEADERS,
        params={"token": token},
        json={
            "enableDhcpV4": True,
            "interfaceUsage": "sharedIp"
        },
        verify=False,
        timeout=10
    )

    print_ok("DHCP mode set")


# =========================================================
# STEP 4: DHCP SUBNET
# =========================================================

def set_dhcp_subnet(vlan_id, service, subnet_name, token, ip=None):
    network = f"192.168.{vlan_id}.0/24"

    print_info(f"DHCP subnet -> {network}")

    req(
        "PUT",
        f"{base(ip)}/service-container/{service}/dhcp/subnets/{subnet_name}",
        headers=HEADERS,
        params={"token": token},
        json={
            "properties": {
                "subnet": network,
                "interface": "p1",
                "ranges": [
                    {
                        "startIp": f"192.168.{vlan_id}.10",
                        "endIp": f"192.168.{vlan_id}.100"
                    }
                ],
                "routers": [f"192.168.{vlan_id}.1"],
                "dnsServers": [f"192.168.{vlan_id}.1"]
            }
        },
        verify=False,
        timeout=10
    )

    print_ok("DHCP subnet configured")


# =========================================================
# ACTIVATION
# =========================================================

def activate(ip=None):
    print_info("Triggering network activation")

    try:
        requests.post(
            f"{ctrl(ip)}/box/net/activate/soft",
            headers=HEADERS,
            verify=False,
            timeout=10
        )
    except:
        pass

    print_ok("Activation triggered")


# =========================================================
# MAIN ENTRY (MATCHES YOUR main.py EXACTLY)
# =========================================================

def configure_cgf(vlan_id, service="DHCP", subnet_name="LAN"):
    mgmt_ip = VLAN_IP_MAP[vlan_id]

    # STEP 1: MANAGEMENT
    token = begin()
    try:
        set_management(vlan_id, token)
        commit(token)

        activate()
        time.sleep(20)

        wait_for_ip(mgmt_ip)
        wait_for_api()

    except Exception as e:
        print_err(f"Management failed: {e}")
        rollback(token)
        raise

    # STEP 2: LAN + DHCP
    token = begin()
    try:
        set_lan(vlan_id, token)
        set_dhcp_mode(token)
        set_dhcp_subnet(vlan_id, service, subnet_name, token)

        commit(token)

        activate(mgmt_ip)
        print_ok(f"CGF configured -> {mgmt_ip}")

    except Exception as e:
        print_err(f"Config failed: {e}")
        rollback(token, mgmt_ip)
        raise