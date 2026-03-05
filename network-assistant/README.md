# Network Topology Assistant

A Cisco Network Assistant-style tool that logs into switches via SSH, discovers neighbors using CDP and LLDP, and builds an interactive topology map in your browser.

## Features

- **SSH-based discovery** — connects to Cisco IOS/IOS-XE/NX-OS and Arista EOS devices via netmiko
- **CDP + LLDP** — discovers neighbors using both protocols for maximum coverage
- **Recursive crawling** — starts from seed devices and crawls hop-by-hop up to a configurable depth
- **Parallel polling** — multiple SSH sessions run concurrently for fast discovery
- **Interactive topology** — vis-network.js graph with click-to-inspect, drag, zoom, and physics-based layout
- **Live progress** — real-time logs and topology updates during discovery
- **Web-based config** — configure credentials and seed devices from the browser
- **Export** — download topology data as JSON

## Quick Start

```bash
cd network-assistant

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp config.yaml.example config.yaml
# Edit config.yaml with your seed switch IPs and credentials

# Run
python app.py
```

Open http://localhost:5000 in your browser.

## Usage

1. **Configure** — enter default credentials and add seed device IPs in the Config tab (or edit `config.yaml`)
2. **Discover** — click "Discover Network" to start crawling
3. **Explore** — click devices in the topology to see details, links, and platform info
4. **Export** — click "Export JSON" to download the topology data

## Configuration

See `config.yaml.example` for all options. Key settings:

| Setting | Description |
|---|---|
| `seed_devices` | Starting switch IPs |
| `defaults.username/password` | SSH credentials |
| `defaults.device_type` | `cisco_ios`, `cisco_xe`, `cisco_nxos`, `arista_eos` |
| `discovery.max_hops` | How far from seeds to crawl (default: 10) |
| `discovery.protocols` | `["cdp", "lldp"]` |
| `discovery.allowed_prefixes` | Restrict discovery to specific subnets |
| `discovery.max_workers` | Concurrent SSH sessions (default: 5) |

## Requirements

- Python 3.9+
- Network access to managed switches (SSH)
- CDP and/or LLDP enabled on network devices
