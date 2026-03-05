"""
Parsers for CDP and LLDP neighbor output from Cisco IOS/IOS-XE/NX-OS devices.
"""

import re


def parse_cdp_neighbors_detail(output):
    """Parse 'show cdp neighbors detail' output.

    Returns a list of neighbor dicts:
        {
            "device_id": str,
            "ip_address": str,
            "platform": str,
            "capabilities": str,
            "local_interface": str,
            "remote_interface": str,
        }
    """
    neighbors = []
    # Split into per-neighbor blocks delimited by dashes
    blocks = re.split(r"-{5,}", output)

    for block in blocks:
        if not block.strip():
            continue

        neighbor = {}

        m = re.search(r"Device ID:\s*(\S+)", block)
        if m:
            neighbor["device_id"] = m.group(1).split(".")[0]  # strip domain
        else:
            continue  # skip blocks without a device ID

        # IP address — may appear as "IP address:" or "IPv4 Address:" or
        # "Management address(es):" followed by the IP on next line
        m = re.search(
            r"(?:IP(?:v4)?\s*[Aa]ddress|Management address)\s*:\s*([\d.]+)", block
        )
        if m:
            neighbor["ip_address"] = m.group(1)
        else:
            neighbor["ip_address"] = ""

        m = re.search(r"Platform:\s*(.+?)(?:,|$)", block, re.MULTILINE)
        neighbor["platform"] = m.group(1).strip() if m else ""

        m = re.search(r"Capabilities:\s*(.+?)$", block, re.MULTILINE)
        neighbor["capabilities"] = m.group(1).strip() if m else ""

        m = re.search(
            r"Interface:\s*(\S+)\s*,\s*Port ID \(outgoing port\):\s*(\S+)", block
        )
        if m:
            neighbor["local_interface"] = _normalize_intf(m.group(1))
            neighbor["remote_interface"] = _normalize_intf(m.group(2))
        else:
            neighbor["local_interface"] = ""
            neighbor["remote_interface"] = ""

        neighbor["protocol"] = "cdp"
        neighbors.append(neighbor)

    return neighbors


def parse_lldp_neighbors_detail(output):
    """Parse 'show lldp neighbors detail' output.

    Returns a list of neighbor dicts with the same schema as CDP parser.
    """
    neighbors = []
    blocks = re.split(r"-{5,}", output)

    for block in blocks:
        if not block.strip():
            continue

        neighbor = {}

        m = re.search(r"System Name:\s*(\S+)", block)
        if m:
            neighbor["device_id"] = m.group(1).split(".")[0]
        else:
            # Fall back to Chassis id
            m = re.search(r"Chassis id:\s*(\S+)", block)
            if m:
                neighbor["device_id"] = m.group(1)
            else:
                continue

        m = re.search(r"Management Addresses?:\s*\n\s*IP:\s*([\d.]+)", block)
        if m:
            neighbor["ip_address"] = m.group(1)
        else:
            # Alternate format
            m = re.search(r"IP:\s*([\d.]+)", block)
            neighbor["ip_address"] = m.group(1) if m else ""

        m = re.search(r"System Description:\s*\n\s*(.+?)$", block, re.MULTILINE)
        neighbor["platform"] = m.group(1).strip() if m else ""

        m = re.search(r"System Capabilities:\s*(.+?)$", block, re.MULTILINE)
        neighbor["capabilities"] = m.group(1).strip() if m else ""

        m = re.search(r"Local Intf:\s*(\S+)", block)
        neighbor["local_interface"] = _normalize_intf(m.group(1)) if m else ""

        m = re.search(r"Port id:\s*(\S+)", block)
        neighbor["remote_interface"] = _normalize_intf(m.group(1)) if m else ""

        neighbor["protocol"] = "lldp"
        neighbors.append(neighbor)

    return neighbors


def parse_hostname(output):
    """Extract hostname from 'show run | include hostname' output."""
    m = re.search(r"hostname\s+(\S+)", output)
    return m.group(1) if m else None


def parse_version_brief(output):
    """Extract platform and software info from 'show version' output."""
    info = {"platform": "", "software": "", "serial": ""}

    m = re.search(r"[Cc]isco\s+(\S+).*?(?:processor|memory)", output)
    if m:
        info["platform"] = m.group(1)

    m = re.search(r"(?:IOS|Software).*?Version\s+([\S]+)", output)
    if m:
        info["software"] = m.group(1).rstrip(",")

    m = re.search(r"[Bb]oard ID\s+(\S+)", output)
    if not m:
        m = re.search(r"[Pp]rocessor board ID\s+(\S+)", output)
    if m:
        info["serial"] = m.group(1)

    return info


def _normalize_intf(name):
    """Shorten interface names to standard abbreviations."""
    replacements = [
        (r"^GigabitEthernet", "Gi"),
        (r"^FastEthernet", "Fa"),
        (r"^TenGigabitEthernet", "Te"),
        (r"^TwentyFiveGigE", "Twe"),
        (r"^FortyGigabitEthernet", "Fo"),
        (r"^HundredGigE", "Hu"),
        (r"^Ethernet", "Eth"),
        (r"^Port-channel", "Po"),
        (r"^Loopback", "Lo"),
        (r"^Vlan", "Vl"),
        (r"^mgmt", "mgmt"),
    ]
    for pattern, repl in replacements:
        name = re.sub(pattern, repl, name)
    return name
