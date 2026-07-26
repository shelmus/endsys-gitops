# USB Device Passthrough on Talos OS

This is an optional recipe for direct USB device access (e.g. a Z-Wave or
Zigbee stick), for use if and when a workload needs to talk to a physical
device attached to a specific node. It is not part of the Home Assistant
household-dashboard baseline, which runs without any USB/hostPath device and
without node pinning.

## Finding Device Paths

Talos Linux is immutable — there is no SSH access. Use `talosctl` to interact with nodes.

### List USB Devices

```bash
# Show all connected USB devices on a node
talosctl -n <node-ip> get usb-devices
```

### Find Serial Device Paths

```bash
# List /dev/serial/by-id for stable device symlinks
talosctl -n <node-ip> ls /dev/serial/by-id

# Example output:
# /dev/serial/by-id/usb-Silicon_Labs_HubZ_Smart_Home_Controller-if01-port0
# /dev/serial/by-id/usb-Zooz_800_Z-Wave_Stick_...-if00-port0
```

### Verify a Specific Device

```bash
# Read the symlink target to see the underlying /dev/ttyXXX
talosctl -n <node-ip> read /dev/serial/by-id/<device-name>

# Check dmesg for USB device attach/detach events
talosctl -n <node-ip> dmesg | grep -i usb
talosctl -n <node-ip> dmesg | grep -i tty
```

### Identify Device Details

```bash
# Full device info (vendor ID, product ID, serial number)
talosctl -n <node-ip> dmesg | grep -i zooz
```

## Using the Device Path

Once you have the path from `/dev/serial/by-id/`, use it in the Helm values:

```yaml
additionalVolumes:
  - name: zwave-usb
    hostPath:
      path: /dev/serial/by-id
      type: Directory

additionalMounts:
  - name: zwave-usb
    mountPath: /dev/serial/by-id
    readOnly: true
```

As a last resort, when a workload needs direct access to a physical device,
grant the minimum device exposure and permissions the workload actually
requires: expose only the intended device path and add only an explicitly
required supplemental group or Linux capability. Do not reach for
`securityContext.privileged: true` by default. Pin the pod to a specific node
with a `nodeSelector` only when the physical device is actually attached to
that node.

In Home Assistant, configure the Z-Wave integration with the full path:

```
/dev/serial/by-id/usb-Zooz_800_Z-Wave_Stick_...-if00-port0
```

## Why `/dev/serial/by-id`

Always use `/dev/serial/by-id/` paths instead of `/dev/ttyUSB0` or `/dev/ttyACM0`. The `by-id` paths are stable symlinks based on device serial numbers and won't change if USB ports are reordered or the node reboots.
