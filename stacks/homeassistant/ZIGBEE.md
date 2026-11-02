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

### Sonoff iPlug S60ZBTPF (smart plug with power metering)

This plug powers the server itself, so it must never switch off. It's also a router.

- **Pairing:** pair it on a different socket, with the server **not** plugged into it,
  since the button may toggle the relay. Hold the button for about 5 seconds, until the
  LED flashes quickly.
- **Before the server goes back on it:**
  - In Zigbee2MQTT (*Devices → the plug → Exposes*), set *Power-on behavior* to `on`, so
    the plug comes back on after a power cut and the server can boot.
  - Leave overload protection (`outlet_control_protect`) off and inching control
    (`inching_control_set`, which switches the outlet back after a delay) disabled; both
    can cut the power by themselves.
  - In Home Assistant, disable the plug's switch entity. The power and energy readings
    keep working.
  - The plug has no child lock, so a press on its button still cuts the power. Keep it
    where nobody bumps it.

  Its features are listed on the
  [Zigbee2MQTT device page](https://www.zigbee2mqtt.io/devices/S60ZBTPF.html).
- **Moving the server onto it:** shut the server down, plug it into the S60, switch the
  S60 on, and boot.

### Sonoff TRVZB (radiator valve, first generation: 3 × AA, no colour display)

Mount it first, pair it second. Sources: the
[Zigbee2MQTT device page](https://www.zigbee2mqtt.io/devices/TRVZB.html) and
[Sonoff's help page](https://help.sonoff.tech/docs/trvzb).

1. **Mount and calibrate.** Screw it fully onto the valve thread (M30×1.5 needs no
   adapter; Danfoss RA, RAV and RAVL each need their matching one). With the batteries
   in, the display shows `FS` or `RD`: press the top button, it shows `,,7` and the motor
   runs through the valve's travel while the display flashes. When the flashing stops,
   hold the top button for about 5 seconds until the temperature shows. No temperature
   means the calibration failed, usually because of the mounting.
2. **Pair.** In manual mode, turn the dial counter-clockwise until the display shows `OF`,
   then hold the top button for 3 seconds. The signal icon flashes; pairing mode stays
   open for about 3 minutes.
3. **Test.** Set the mode to `off` and wait an hour: the radiator, including the return
   pipe, should be completely cold. A radiator that stays warm on the valve side means
   the valve doesn't fully close; check the mount and calibrate again.

- **Recalibrating** has no Zigbee command: take it off, reinsert the batteries, and go
  through step 1 again. On its own, it opens and closes the valve once a week (Monday
  around midday) against calcification.
- **Frost protection** opens the valve below its set temperature even in `off` mode.
- **Switching points:** the valve opens 1 °C below the target and closes at it.
  *Temperature accuracy* (−1 to −0.2 °C, firmware 1.3.0+) narrows the gap, at the cost of
  more valve movement. *Smart temperature control* opens the valve gradually (PID)
  instead; temperature accuracy is then unavailable.
- **Mode:** `heat` regulates to the setpoint set from Home Assistant; `auto` follows a
  schedule stored on the device, which competes with Home Assistant, so don't use it.
  The heating schedule is in [HOMEASSISTANT.md](HOMEASSISTANT.md#heating).

#### Using a room sensor instead of the built-in one

The TRV measures next to the radiator and reads high. It can regulate on another sensor's
reading instead, but doesn't fetch it itself: Home Assistant has to keep sending it.

1. In Zigbee2MQTT, set *Temperature sensor select* to `remote_temperature` on every TRV
   in the room.
2. In Home Assistant, add an automation (*Edit in YAML*) that sends the room sensor's
   temperature to the TRV's *External temperature input*. Entity IDs are under
   *Entities → the entity → ⚙ Settings*:

   ```yaml
   alias: Bedroom radiators use the room sensor
   mode: single
   triggers:
     - trigger: state
       entity_id: sensor.bedroom_climate_temperature
     # The sensor only reports on change; resend regularly so the TRV doesn't
     # consider the remote source offline
     - trigger: time_pattern
       minutes: "/10"
   conditions:
     - condition: template
       value_template: "{{ states('sensor.bedroom_climate_temperature') | is_number }}"
   actions:
     - action: number.set_value
       # List the TRVs explicitly: an area target would also set their other number
       # entities, like the calibration offset
       target:
         entity_id:
           - number.bedroom_radiator_1_external_temperature_input
           - number.bedroom_radiator_2_external_temperature_input
       data:
         value: "{{ states('sensor.bedroom_climate_temperature') | float | round(1) }}"
   ```

3. Check the TRV's *Exposes* page: *External temperature input* holds the sensor's value,
   and *Temperature sensor select* stays on `remote_temperature`. If it switches to
   `remote_source_offline`, updates stopped and the TRV fell back to its own sensor; it
   switches back once they resume.

Place the sensor away from the radiator, out of direct sun, and not on an outside wall.

### IKEA TRÅDFRI bulb LED1937T5 (E27, white spectrum, T120 cylinder, opal, 470 lm)

Zigbee2MQTT identifies it as `TRADFRIbulbT120E27WSopal470lm`. White spectrum means
dimmable with adjustable colour temperature, but no colours. It's a router, as long as it
has power: on a wall switch that's often off, the network loses that route, so it's best
left powered and switched over Zigbee.

- **Pairing:** it has no button; a reset puts it in pairing mode. With the bulb close to
  the coordinator and *Permit join* on, start with it on, then switch it off and on
  **6 times**: short "on"s, slightly longer "off"s, and leave it on after the 6th. It
  blinks or fades to confirm the reset and joins by itself. If not, the timing was off;
  try again. Zigbee2MQTT notes that 7 cycles sometimes fails on similar models.
- **Firmware:** IKEA ships updates; Zigbee2MQTT offers them under *OTA*.

### IKEA STYRBAR remote (E2001/E2002)

Battery-powered (2 × AAA), so an end device. Source: the
[Zigbee2MQTT device page](https://www.zigbee2mqtt.io/devices/E2001_E2002_E2313.html).

- **Pairing:** pair it through the coordinator, not directly to a bulb as IKEA's leaflet
  describes. With *Permit join* on, press the pairing button under the back cover (next
  to the batteries) **4 times**; a red light pulses until it has joined. If not, press
  the big on button (☀) 6 times first, then the pairing button 4 times.
- **Actions:** each press is published on `zigbee2mqtt/<friendly name>` as `action`:
  `on`, `off`, `brightness_move_up`, `brightness_move_down`, `brightness_stop`, and
  `arrow_left_click`/`_hold`/`_release` and the same for `arrow_right`. Home Assistant
  turns them into light commands, see
  [HOMEASSISTANT.md](HOMEASSISTANT.md#lighting).
- **No direct binding** to the bulb: Zigbee2MQTT warns that a bound remote may spam the
  network, drain its battery or disconnect when the bound device goes offline.
- **Sleeps** between presses and doesn't answer Zigbee2MQTT then; press a button to wake
  it, e.g. for an OTA update.
- **Checking the topic:** Home Assistant's *Settings → Devices & services → MQTT →
  Configure → Listen to a topic* with `zigbee2mqtt/#` shows each press. Copy the topic
  from there: a phone may have typed `’` instead of `'` in the friendly name.
