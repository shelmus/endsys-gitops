# USB Device Passthrough on Talos OS

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

The pod must run with `securityContext.privileged: true` and a `nodeSelector` pinning it to the node with the device.

In Home Assistant, configure the Z-Wave integration with the full path:

```
/dev/serial/by-id/usb-Zooz_800_Z-Wave_Stick_...-if00-port0
```

## Why `/dev/serial/by-id`

Always use `/dev/serial/by-id/` paths instead of `/dev/ttyUSB0` or `/dev/ttyACM0`. The `by-id` paths are stable symlinks based on device serial numbers and won't change if USB ports are reordered or the node reboots.
