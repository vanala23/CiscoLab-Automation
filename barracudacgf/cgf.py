import requests
import urllib3
import time

from config import CGF_MGMT_IP, CGF_TOKEN, VLAN_IP_MAP
from utils import print_ok, print_info, print_err

urllib3.disable_warnings()

HEADERS = {
    "X-API-Token": CGF_TOKEN,
    "Content-Type": "application/json"
}

# =========================================================
# STATE (CRITICAL for IP switch)
# =========================================================

CURRENT_IP = None


def active_ip(ip=None):
    """Always resolve correct active CGF IP"""
    return ip or CURRENT_IP or CGF_MGMT_IP


def base(ip=None):
    return f"https://{active_ip(ip)}:8443/rest/config/v1"


def ctrl(ip=None):
    return f"https://{active_ip(ip)}:8443/rest/control/v1"


# =========================================================
# SESSION
# =========================================================

def begin(ip=None):
    r = requests.post(
        f"{base(ip)}/begin",
        headers=HEADERS,
        verify=False,
        timeout=10
    )
    r.raise_for_status()
    return r.json()["token"]


def commit(token, ip=None):
    requests.post(
        f"{base(ip)}/commit",
        headers=HEADERS,
        params={"token": token},
        verify=False,
        timeout=10
    )


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
# WAIT HELPERS
# =========================================================

def wait_for_cgf(ip=None):
    print_info("Waiting for CGF API...")

    for _ in range(600):
        try:
            r = requests.get(
                f"{base(ip)}/box/network/management",
                headers=HEADERS,
                verify=False,
                timeout=3
            )
            if r.status_code in (200, 401):
                print_ok("CGF reachable")
                time.sleep(60)
                return
        except:
            pass
        time.sleep(1)

    raise TimeoutError("CGF unreachable")


def wait_for_ip(ip):
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
        time.sleep(1)

    raise TimeoutError(f"CGF not reachable at {ip}")


# =========================================================
# MANAGEMENT IP (STEP 1)
# =========================================================

def set_management(vlan_id, token, ip=None):
    global CURRENT_IP

    new_ip = VLAN_IP_MAP[vlan_id]
    print_info(f"Setting management IP -> {new_ip}")

    r = requests.patch(
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

    if r.status_code >= 400:
        print_err(r.text)

    r.raise_for_status()

    CURRENT_IP = new_ip
    print_ok("Management IP updated")


# =========================================================
# ADDITIONAL ADDRESS (LAN on p2)
# =========================================================

def set_lan_additional_ip(vlan_id, token, ip=None):
    lan_ip = f"192.168.{vlan_id}.1"
    name = "LAN"   # bleibt konstant, aber wir UPSERTEN

    print_info(f"Setting LAN IP -> {lan_ip}")

    url = f"{base(ip)}/box/network/additional-address/v4/{name}"

    r = requests.put(
        url,
        headers=HEADERS,
        params={"token": token},
        json={
            "name": name,
            "properties": {
                "ipAddress": lan_ip,
                "mask": "255.255.255.0",
                "interface": "p2",
                "respondsToPing": True,
                "isManagementIp": False,
                "sharedIps": [
                    {
                        "ipAddress": lan_ip,
                        "alias": "none",
                        "respondsToPing": True
                    }
                ],
                "directInternetAccess": False,
                "providerClass": "bulk",
                "routeMetric": 1
            }
        },
        verify=False,
        timeout=10
    )

    r.raise_for_status()
    print_ok("LAN updated (UPSERT)")


# =========================================================
# DHCP
# =========================================================

def set_dhcp(vlan_id, service, subnet_name, token, ip=None):
    network = f"192.168.{vlan_id}.0/24"

    print_info(f"Configuring DHCP subnet {subnet_name} -> {network}")

    r = requests.put(
        f"{base(ip)}/service-container/{service}/dhcp/subnets/{subnet_name}",
        headers=HEADERS,
        params={"token": token},
        json={
            "properties": {
                "subnet": network,
                "interface": "p2",
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

    if r.status_code >= 400:
        print_err(r.text)

    r.raise_for_status()
    print_ok("DHCP configured")


# =========================================================
# NETWORK ACTIVATION
# =========================================================

def activate(ip=None):
    print_info("Trigger network activation")

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
# MAIN FLOW
# =========================================================

def configure_cgf(vlan_id, service="DHCP", subnet_name="LAN"):
    mgmt_ip = VLAN_IP_MAP[vlan_id]

    # -------------------------
    # STEP 1: MANAGEMENT
    # -------------------------
    token = begin()
    try:
        set_management(vlan_id, token)
        commit(token)
        activate()
    except Exception as e:
        print_err(f"Management failed: {e}")
        rollback(token)
        raise

    time.sleep(10)

    wait_for_ip(mgmt_ip)

    # -------------------------
    # STEP 2: LAN + DHCP
    # -------------------------
    token = begin()

    try:
        set_lan_additional_ip(vlan_id, token)
        set_dhcp(vlan_id, service, subnet_name, token)

        commit(token)
        activate(mgmt_ip)

        print_ok(f"CGF configured -> {mgmt_ip}")

    except Exception as e:
        print_err(f"Config failed: {e}")
        rollback(token, mgmt_ip)
        raise