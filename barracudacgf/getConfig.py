import requests
import urllib3
import json
import sys

urllib3.disable_warnings()

IP = sys.argv[1] if len(sys.argv) > 1 else input("IP: ")
TOKEN = sys.argv[2] if len(sys.argv) > 2 else input("Token: ")

HEADERS = {"X-API-Token": TOKEN}

def get(path):
    r = requests.get(f"https://{IP}:8443{path}", headers=HEADERS, verify=False, timeout=5)
    return r.json()

config = {
    "management": get("/rest/config/v1/box/network/management"),
    "physical_interfaces": get("/rest/config/v1/box/network/interfaces/physical?expand=true"),
    "vlans": get("/rest/config/v1/box/network/vlans"),
    "shared_networks_v4": get("/rest/config/v1/box/network/shared-network/v4"),

    "service_container": get("/rest/config/v1/service-container"),
    "service_dhcp": get("/rest/config/v1/service-container/DHCP"),

    "dhcp_common": get("/rest/config/v1/service-container/DHCP/dhcp"),
    "dhcp_common_expand": get("/rest/config/v1/service-container/DHCP/dhcp?expand=true"),
    "dhcp_common_meta": get("/rest/config/v1/service-container/DHCP/dhcp/meta"),

    "dhcp_subnets": get("/rest/config/v1/service-container/DHCP/dhcp/subnets"),
    "dhcp_subnet_lan": get("/rest/config/v1/service-container/DHCP/dhcp/subnets/LAN"),
    "dhcp_operative": get("/rest/dhcp/v1/subnets"),
}

print(json.dumps(config, indent=2))