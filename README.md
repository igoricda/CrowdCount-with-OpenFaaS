# CrowdCount-with-OpenFaaS
Repository with files used in my scientific initiation, using serveless combined with inference models in fog and edge devices

## Devices

Fog:
- Conventional server (Ryzen 7 5700G with 64GB RAM)

Edge:
- Raspberry Pi 4B
-  Repurposed XP4 TVBox (SoC Amlogic S905x4) with armbian OS
  
On the server, OpenFaaS CE was used as serverless framework, while the edge devices, used faasd, OpenFaaS lightweight version, appropriate for the edge.

## Install walkthrough

### Edge
Both devices used the same process to install faasd:

1. Via CLI, clone the faasd repository with:
'''
git clone https://github.com/openfaas/faasd
'''
2. Change to the cloned directory with: '''cd faasd'''
