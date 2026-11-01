# Zigbee

How the Zigbee coordinator is set up and how devices are paired. The `homeassistant` stack
itself is set up in step 19 of the main [README](../../README.md).

Zigbee2MQTT owns the coordinator and talks to the devices. It publishes them over MQTT,
and Home Assistant picks them up through its MQTT integration. Home Assistant never talks
to the coordinator itself.

## Coordinator: Sonoff Zigbee 3.0 USB Dongle Plus (P)

- **Chip:** TI CC2652P, Z-Stack firmware, so `ZIGBEE_ADAPTER=zstack`
- **Path:** `ZIGBEE_DEVICE=/dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_...-if00-port0`
  (the full name is in `ls -l /dev/serial/by-id/`)

1. Plug the dongle in with a USB extension cable, away from the PC case and USB 3 ports.
   USB 3 and the PC itself put out noise in the 2.4 GHz band that Zigbee uses.
2. Check that Zigbee2MQTT found it:

   ```bash
   cd /opt/homelab-ber/stacks/homeassistant
   docker compose logs zigbee2mqtt | grep -iE 'coordinator|zigbee-herdsman|error'
   ```

   It should log `zigbee-herdsman started` and the coordinator's firmware version. In the
   frontend at `https://zigbee2mqtt.local.ber.nvcode.com`, *Settings → Bridge* shows the
   coordinator and the network it runs (channel, PAN ID).
3. In Home Assistant, **ignore** the discovered "Zigbee Home Automation" (ZHA) entry under
   *Settings → Devices & services → Discovered*. Home Assistant spots the dongle over USB
   and offers its own Zigbee integration, but the dongle is passed only to the
   Zigbee2MQTT container and a serial port can be used by one program at a time, so
   setting up ZHA fails.

### Channel

The network runs on **Zigbee channel 25**. Zigbee shares the 2.4 GHz band with Wi-Fi: the
Speedport is on Wi-Fi channel 6 and the neighbours use 1, 2, 6 and 11, and channel 25
(2475 MHz) sits above all of them. Onboarding first picked channel 11, which lies under
Wi-Fi channels 1 and 2.

The channel can only be changed before any device is paired; afterwards every device has
to be paired again. *Settings → Bridge* in the frontend shows the running network.

### Back up the network

On first start Zigbee2MQTT generates the network key, PAN ID and channel and writes them
to `/srv/homeassistant/zigbee2mqtt/configuration.yaml`. It also keeps
`coordinator_backup.json` there. Paired devices are tied to these values: losing them or
changing the channel means pairing every device again. Back up the whole
`/srv/homeassistant/zigbee2mqtt` directory, and keep it out of git, since it holds the
network key.

## Pairing devices

1. In the Zigbee2MQTT frontend, click *Permit join (All)*. Joining stays open for a few
   minutes, counting down on the button.
2. Put the device in pairing mode (see below), close to the coordinator.
3. Zigbee2MQTT logs the join and runs an *interview*, reading what the device is and what
   it can do. Wait until the device shows up as *Supported* under *Devices*.
4. Rename it (*Devices → the device → Settings → Friendly name*) to something like
   `living-room-climate`, with *Update Home Assistant entity ID* checked. Home Assistant
   gets the device through MQTT discovery; it appears under the MQTT integration.
5. Close joining again (*Disable join*), then move the device to its final place.

Battery devices are end devices and don't relay for others. Mains-powered devices (plugs,
bulbs) act as routers and extend the network's range.

### Sonoff SNZB-02D (temperature and humidity, LCD)

- **Pairing mode:** hold the button on the back for about 5 seconds, until the signal icon
  on the display blinks.
- After pairing, the device's *Exposes* tab shows temperature, humidity and battery. Its
  *Settings (specific)* tab has calibration offsets, in case the readings differ from a
  reference thermometer.
