# Home Assistant

How Home Assistant is configured: helpers, automations and dashboards. The `homeassistant`
stack itself is set up in step 19 of the main [README](../../README.md); Zigbee devices
are paired as described in [ZIGBEE.md](ZIGBEE.md).

Automations are created in the UI (*Settings → Automations → Create automation*). Their
YAML is pasted through *⋮ → Edit in YAML*. Entity IDs are under *Settings → Devices &
services → Entities → the entity → ⚙ Settings*; the ones below are examples.

## Heating schedule

The radiator valves (TRVZB) stay in `heat` mode. Home Assistant sets their target
temperature: comfort while a Schedule helper is on, eco while it's off. Their own
on-device schedule (`auto` mode) isn't used, since it would compete with this one.

1. Create the schedule under *Settings → Devices & services → Helpers → Create helper →
   Schedule*, e.g. `Bedroom heating`, and drag in the blocks when the room should be
   warm. This creates `schedule.bedroom_heating`, which is `on` inside a block.
2. Add the automation:

   ```yaml
   alias: Bedroom heating follows the schedule
   mode: single
   triggers:
     - trigger: state
       entity_id: schedule.bedroom_heating
     # Reapply after a Home Assistant restart
     - trigger: homeassistant
       event: start
     # Reapply when automations are saved or reloaded
     - trigger: event
       event_type: automation_reloaded
   actions:
     - action: climate.set_temperature
       # Every thermostat in the room, including ones added later
       target:
         area_id: n_v_bedroom
       data:
         hvac_mode: heat
         temperature: "{{ 21 if is_state('schedule.bedroom_heating', 'on') else 17 }}"
   ```

   21 °C is the comfort and 17 °C the eco temperature.

- A manual change, on the dial or in Home Assistant, holds until the schedule next
  switches.
- The automation runs when the schedule switches either way, not continuously. Until the
  first switch it shows as never triggered; *⋮ → Run actions* applies it right away.
- The automation targets the room's area, so a room with two radiators needs nothing
  extra. Each room gets its own schedule and automation. *Developer tools → Template*
  with `{{ areas() }}` lists the area IDs; an ID keeps the area's original name when the
  area is renamed.
- Change the times by editing the schedule helper; the automation stays as it is.
