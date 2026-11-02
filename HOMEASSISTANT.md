# Home Assistant

How Home Assistant is configured: helpers, automations and dashboards. The `homeassistant`
stack itself is set up in step 19 of the main [README](README.md); Zigbee devices
are paired as described in [ZIGBEE.md](ZIGBEE.md).

Automations are created in the UI (*Settings → Automations → Create automation*). Their
YAML is pasted through *⋮ → Edit in YAML*. Entity IDs are under *Settings → Devices &
services → Entities → the entity → ⚙ Settings*.

## Heating

The radiator valves (TRVZB) stay in `heat` mode, and Home Assistant sets their target
temperature. Their own on-device schedule (`auto` mode) isn't used, since it would compete
with this one.

- **Heating season** (a global toggle): when off, every heating automation is disabled
  and every valve is set to its lowest temperature. When on, they're enabled again.
- **Per room**, during the heating season: **comfort** while the room's pre-heat toggle
  is on; otherwise **eco** while its away toggle is on, **comfort** while the schedule is
  on or someone is home, and **eco** outside it.

Automations that belong to the heating carry the label `heating`; the season automation
switches them by that label, so a new room's automations only need the label.

### Heating season

1. **Toggle:** *Settings → Devices & services → Helpers → Create helper → Toggle*, named
   `Heating season` (`input_boolean.heating_season`).
2. **Label:** *Settings → Areas, labels & zones → Labels*, create `heating`, and give it
   to every room's heating automations (*Settings → Automations*, select them, *Add
   label*). Not to the season automation itself, or it would switch itself off.
3. **Automation:**

   ```yaml
   alias: Heating season
   description: >-
     On: enables the heating automations and applies them. Off: disables them and sets
     every radiator valve to its lowest temperature.
   mode: single
   triggers:
     - trigger: state
       entity_id: input_boolean.heating_season
       to: ~
   actions:
     - if:
         - condition: state
           entity_id: input_boolean.heating_season
           state: "on"
       then:
         - action: automation.turn_on
           target:
             label_id: heating
         # Apply the current schedule, presence and away state right away
         - action: automation.trigger
           target:
             label_id: heating
       else:
         # Disable first, so no automation overrides the minimum temperature
         - action: automation.turn_off
           target:
             label_id: heating
         - repeat:
             for_each: "{{ states.climate | map(attribute='entity_id') | list }}"
             sequence:
               - action: climate.set_temperature
                 target:
                   entity_id: "{{ repeat.item }}"
                 data:
                   hvac_mode: heat
                   temperature: "{{ state_attr(repeat.item, 'min_temp') }}"
   ```

Whether an automation is enabled survives restarts, so the season state does too. With
the room sensor automation off, the TRVs fall back to their own sensor, which doesn't
matter at the minimum temperature.

### N&V bedroom

Area `bedroom`, two TRVs. Its heating automation and the room sensor one from
[ZIGBEE.md](ZIGBEE.md#using-a-room-sensor-instead-of-the-built-in-one) carry the
`heating` label.

1. **Schedule:** *Create helper → Schedule*, named `N&V Bedroom heating`
   (`schedule.n_v_bedroom_heating`). Drag in the blocks when the room should be warm;
   it's `on` inside a block.
2. **Temperatures:** two helpers of type *Number*, min 5, max 30, step 0.5, unit °C:
   `N&V Bedroom comfort temperature` (`input_number.n_v_bedroom_comfort_temperature`) and
   `N&V Bedroom eco temperature` (`input_number.n_v_bedroom_eco_temperature`).
3. **Away:** *Create helper → Toggle*, named `N&V Bedroom away`
   (`input_boolean.n_v_bedroom_away`), in the bedroom area. A *Button* helper wouldn't
   do: it has no state.
4. **Pre-heat:** *Create helper → Toggle*, named `N&V Bedroom pre-heat`
   (`input_boolean.n_v_bedroom_pre_heat`), in the bedroom area. Switched on from the
   phone on the way home, it warms the room to comfort, even while away is on. It
   switches off on arrival or after 4 hours, whichever comes first.
5. **Presence:** the Home Assistant Companion app on the phone reports its location;
   under *Settings → People*, assign its device tracker to the person
   (`person.valentin_nemeth`). The app reaches Home Assistant from outside through the
   frpc tunnel. The UI shows the state as *Home*; the actual state is `home`.
6. **Automation**, with the `heating` label:

   ```yaml
   alias: N&V Bedroom heating automation
   description: >-
     Comfort while pre-heating; otherwise eco when away, and comfort while the
     schedule is on or someone is home. Disabled outside the heating season.
   mode: single
   triggers:
     # Reapply when automations are saved or reloaded
     - trigger: event
       event_type: automation_reloaded
     # "to: null" fires on state changes only, not on attribute updates (the person's
     # GPS position changes constantly and would send commands to the TRVs every time)
     - trigger: state
       entity_id:
         - schedule.n_v_bedroom_heating
         - input_number.n_v_bedroom_comfort_temperature
         - input_number.n_v_bedroom_eco_temperature
         - input_boolean.n_v_bedroom_away
         - input_boolean.n_v_bedroom_pre_heat
         - person.valentin_nemeth
       to: null
     # Reapply after a Home Assistant restart
     - trigger: homeassistant
       event: start
   actions:
     - action: climate.set_temperature
       # Every thermostat in the room, including ones added later
       target:
         area_id: bedroom
       data:
         hvac_mode: heat
         temperature: |-
           {% set preheat = is_state('input_boolean.n_v_bedroom_pre_heat', 'on') %}
           {% set away = is_state('input_boolean.n_v_bedroom_away', 'on') %}
           {% set comfort = preheat
                            or (not away
                                and (is_state('schedule.n_v_bedroom_heating', 'on')
                                     or is_state('person.valentin_nemeth', 'home'))) %}
           {{ states('input_number.n_v_bedroom_comfort_temperature') if comfort
              else states('input_number.n_v_bedroom_eco_temperature') }}
   ```

7. **Ending pre-heat**, without the `heating` label, so the toggle is also reset outside
   the heating season:

   ```yaml
   alias: N&V Bedroom pre-heat ends on arrival
   description: 'N&V Bedroom pre-heat ends on arrival or after a time if not arrived'
   mode: single
   triggers:
     - trigger: state
       entity_id: person.valentin_nemeth
       to: home
     - trigger: state
       entity_id: input_boolean.n_v_bedroom_pre_heat
       to: "on"
       for:
         hours: 4
   conditions:
     - condition: state
       entity_id: input_boolean.n_v_bedroom_pre_heat
       state: "on"
   actions:
     - action: input_boolean.turn_off
       target:
         entity_id: input_boolean.n_v_bedroom_pre_heat
   ```

   The 4-hour timer only lives in memory: a Home Assistant restart in between cancels it,
   and pre-heat then stays on until arrival or until it's switched off by hand.

8. **Status sensors**, for the dashboard: *Create helper → Template*, then the entity
   type.
   - *Binary sensor* `N&V Bedroom heating active`, device class *Heat*, on while any TRV
     in the room is heating:
     ```
     {{ area_entities('bedroom') | select('match', 'climate\\.')
        | map('state_attr', 'hvac_action') | select('eq', 'heating')
        | list | count > 0 }}
     ```
   - *Sensor* `N&V Bedroom target temperature`, unit °C, device class *Temperature*,
     state class *Measurement*:
     ```
     {% set targets = area_entities('bedroom') | select('match', 'climate\\.')
                      | map('state_attr', 'temperature') | select('number') | list %}
     {{ targets | max if targets else none }}
     ```

   The TRVZB doesn't report how far its valve is open; *valve opening degree* is a limit
   you set, not its position. *Heating*/*idle* is the live signal.

### Dashboard

The automatic Overview (areas and summaries) takes no custom cards, so the heating has its
own dashboard: *Settings → Dashboards → Add dashboard → New dashboard from scratch*,
`Heating`. Cards are added with the **＋** in a section; Tile cards for the toggles,
Number helpers and status sensors, Thermostat cards for the TRVs, and a History graph of
the room temperature, the target and *heating active*.

### Notes

- An automation only runs on its triggers, not continuously; *⋮ → Run actions* applies
  it right away. A manual change, on the dial or in Home Assistant, holds until the next
  trigger.
- *Developer tools → Template* tests a template before saving, and `{{ areas() }}` lists
  the area IDs. An area ID keeps the area's original name when the area is renamed.
  If an automation doesn't do what it should, its *Traces* show which step failed.
- The valve opens 1 °C below the target and closes at the target. The TRV's *Temperature
  accuracy* (firmware 1.3.0+) narrows this to as little as 0.2 °C; see
  [ZIGBEE.md](ZIGBEE.md).

## Lighting

### Nora's bedlight

A TRÅDFRI white spectrum bulb, controlled by a STYRBAR remote (`Nora's bedlight remote`
in Zigbee2MQTT); both are described in [ZIGBEE.md](ZIGBEE.md). The automation listens to
the remote's MQTT topic; the bulb is `light.nora_s_bedlight`.

- **Press ☀ / ☾:** on / off.
- **Hold ☀ / ☾:** brighter / dimmer, one 20 % step per hold (not smooth dimming).
- **Left / right arrow:** warmer / cooler, 500 K per press, within the bulb's range. If the
  bulb is off, an arrow switches it on; its colour temperature is unknown then, so the
  step starts from 2700 K.

```yaml
alias: Nora's bedlight remote
mode: queued
triggers:
  # Quoted because of the apostrophe; spaces are fine in MQTT topics
  - trigger: mqtt
    topic: "zigbee2mqtt/Nora's bedlight remote"
conditions:
  - condition: template
    value_template: "{{ trigger.payload_json.action | default('') != '' }}"
actions:
  - variables:
      action: "{{ trigger.payload_json.action }}"
      light: light.nora_s_bedlight
      # Kelvin per arrow press
      step: 500
      kelvin: "{{ state_attr(light, 'color_temp_kelvin') | int(2700) }}"
      kelvin_min: "{{ state_attr(light, 'min_color_temp_kelvin') | int(2200) }}"
      kelvin_max: "{{ state_attr(light, 'max_color_temp_kelvin') | int(4000) }}"
  - choose:
      - conditions: "{{ action == 'on' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: "{{ light }}"
      - conditions: "{{ action == 'off' }}"
        sequence:
          - action: light.turn_off
            target:
              entity_id: "{{ light }}"
      - conditions: "{{ action == 'brightness_move_up' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: "{{ light }}"
            data:
              brightness_step_pct: 20
      - conditions: "{{ action == 'brightness_move_down' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: "{{ light }}"
            data:
              brightness_step_pct: -20
      # Left: warmer (lower kelvin)
      - conditions: "{{ action == 'arrow_left_click' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: "{{ light }}"
            data:
              color_temp_kelvin: "{{ [kelvin - step, kelvin_min] | max }}"
      # Right: cooler (higher kelvin)
      - conditions: "{{ action == 'arrow_right_click' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: "{{ light }}"
            data:
              color_temp_kelvin: "{{ [kelvin + step, kelvin_max] | min }}"
```
