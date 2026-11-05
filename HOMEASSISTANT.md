# Home Assistant

How Home Assistant is configured: helpers, automations and dashboards. The `homeassistant`
stack itself is set up in step 19 of the main [README](README.md); Zigbee devices
are paired as described in [ZIGBEE.md](ZIGBEE.md).

Automations are created in the UI (*Settings → Automations → Create automation*). Their
YAML is pasted through *⋮ → Edit in YAML*. Entity IDs are under *Settings → Devices &
services → Entities → the entity → ⚙ Settings*.

## HACS

[HACS](https://hacs.xyz) (Home Assistant Community Store) installs community
integrations and dashboard cards. It was installed into the config directory from the
`homeassistant` stack directory:

```bash
cd /opt/homelab-ber/stacks/homeassistant
docker compose exec -it homeassistant bash -c "wget -O - https://get.hacs.xyz | bash -"
docker compose restart homeassistant
```

It then shows up under *Settings → Devices & services → Add integration → HACS*, which
links it to a GitHub account. Installed from it:

- **apexcharts-card** (frontend): the climate chart on the Heating dashboard.
- **Versatile Thermostat** (integration): the heating control, see [Heating](#heating).

## Heating

[Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat) (VTherm, from
HACS) controls the radiator valves (TRVZB). Each room gets one VTherm, which reads the
room's climate sensor and computes how far the valves open (TPI), then writes that
opening to the TRVs directly. The TRVs stay in `heat` mode, with *Smart temperature
control* off
([ZIGBEE.md](ZIGBEE.md#sonoff-trvzb-radiator-valve-first-generation-3--aa-no-colour-display));
their own regulation and on-device schedule (`auto` mode) aren't used.

- **Heating season** (a global toggle): when off, VTherm's central mode goes to *Stopped*,
  which switches every VTherm and its valves off, and the heating automations are
  disabled. When on, central mode goes back to *Auto* and everything is applied again.
- **Per room**, during the heating season: **comfort** while the room's pre-heat toggle
  is on; otherwise **eco** while its away toggle is on, **comfort** while the schedule is
  on or someone is home, and **eco** outside it.

Automations and VTherm climate entities that belong to the heating carry the label
`heating`; the season automation switches them by that label, so a new room's only need
the label.

### Versatile Thermostat

Installed from HACS (*HACS → search "Versatile Thermostat" → Download*, then restart Home
Assistant). Thermostats are added under *Settings → Devices & services → Add integration →
Versatile Thermostat*; each one is a menu of sections, and *Finalize* appears once every
required section is filled in.

1. **Outdoor temperature**, which TPI uses: *Create helper → Template → Sensor*, named
   `Outdoor temperature` (`sensor.outdoor_temperature`), unit °C, device class
   *Temperature*, state class *Measurement*:
   ```
   {{ state_attr('weather.forecast_home', 'temperature') }}
   ```
2. **Central configuration** (type *Central configuration*), shared by every room:
   - *Main:* outdoor sensor `sensor.outdoor_temperature`, min 7 °C, max 30 °C, step 0.1.
   - *TPI:* the defaults (coef_int 0.6, coef_ext 0.01, minimal activation delay 10 s).
   - *Advanced:* the defaults (safety delay 60 min).
3. **Preset temperatures**, on the *Central configuration* device
   (`number.central_configuration_preset_*`):

   | Preset | Present | Away (absent) |
   |---|---|---|
   | Comfort | 21 °C | = eco |
   | Eco | 16 °C | = eco |
   | Boost | 23 °C | = eco |
   | Frost | 7 °C | 7 °C |

   *Away* is what a preset uses while the room's presence sensor is off. Comfort-away is
   the eco temperature, which is what makes comfort follow presence (see below).
4. **Away temperatures follow eco**, so changing eco on the dashboard also changes what an
   empty room drops to:

   ```yaml
   alias: Heating absent temperatures follow eco
   description: >-
     Keeps Versatile Thermostat's absent temperatures (comfort, eco and boost away) at
     the eco temperature, so an empty room drops to eco whatever eco is set to.
   mode: restart
   triggers:
     - trigger: state
       entity_id: number.central_configuration_preset_eco_temp
       not_to: [unavailable, unknown]
   actions:
     - action: number.set_value
       target:
         entity_id:
           - number.central_configuration_preset_comfort_away_temp
           - number.central_configuration_preset_eco_away_temp
           - number.central_configuration_preset_boost_away_temp
       data:
         value: "{{ trigger.to_state.state }}"
   ```

   Without the `heating` label, so it also works outside the heating season.
5. **Central mode** (`select.central_configuration_central_mode`): *Auto* in the heating
   season, *Stopped* outside it. The season automation sets it.

### Heating season

1. **Toggle:** *Settings → Devices & services → Helpers → Create helper → Toggle*, named
   `Heating season` (`input_boolean.heating_season`).
2. **Label:** *Settings → Areas, labels & zones → Labels*, create `heating`, and give it
   to every room's heating automations and VTherm climate entity. Not to the season
   automation itself, or it would switch itself off.
3. **Automation:**

   ```yaml
   alias: Heating season
   description: >-
     On: Versatile Thermostat's central mode goes to Auto, the heating thermostats to
     heat, and the heating automations are enabled and applied. Off: the automations are
     disabled and central mode goes to Stopped, which switches every VTherm and its valves
     off (the TRVs' own frost protection stays active).
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
         - action: select.select_option
           target:
             entity_id: select.central_configuration_central_mode
           data:
             option: Auto
         - action: climate.set_hvac_mode
           target:
             label_id: heating
           data:
             hvac_mode: heat
         - action: automation.turn_on
           target:
             label_id: heating
         # Apply the current presets right away
         - action: automation.trigger
           target:
             label_id: heating
           # automation.trigger skips conditions by default; keep them
           data:
             skip_condition: false
       else:
         - action: automation.turn_off
           target:
             label_id: heating
         - action: select.select_option
           target:
             entity_id: select.central_configuration_central_mode
           data:
             option: Stopped
   ```

### N&V bedroom

Area `bedroom`, two TRVs, one VTherm (`climate.n_v_bedroom`).

1. **Schedule:** *Create helper → Schedule*, named `N&V Bedroom heating`
   (`schedule.n_v_bedroom_heating`). Drag in the blocks when the room should be warm;
   it's `on` inside a block.
2. **Away:** *Create helper → Toggle*, named `N&V Bedroom away`
   (`input_boolean.n_v_bedroom_away`), in the bedroom area. A *Button* helper wouldn't
   do: it has no state.
3. **Pre-heat:** *Create helper → Toggle*, named `N&V Bedroom pre-heat`
   (`input_boolean.n_v_bedroom_pre_heat`), in the bedroom area. Switched on from the
   phone on the way home, it warms the room to comfort, even while away is on. It
   switches off on arrival or after 4 hours, whichever comes first. The 4 hours are
   counted by a *Timer* helper, also named `N&V Bedroom pre-heat`
   (`timer.n_v_bedroom_pre_heat`), in the bedroom area, duration `04:00:00`, with
   *Restore* on so it keeps running across Home Assistant restarts.
4. **Presence:** the Home Assistant Companion app on the phone reports its location;
   under *Settings → People*, assign its device tracker to the person
   (`person.valentin_nemeth`). The app reaches Home Assistant from outside through the
   frpc tunnel. The UI shows the state as *Home*; the actual state is `home`.
5. **Room presence for VTherm:** *Create helper → Template → Binary sensor*, named
   `N&V Bedroom presence` (`binary_sensor.n_v_bedroom_presence`), device class
   *Occupancy*, in the bedroom area. It's on whenever the room should be at comfort,
   rather than strictly when someone is there:
   ```
   {{ is_state('person.valentin_nemeth', 'home')
      or is_state('input_boolean.n_v_bedroom_pre_heat', 'on')
      or is_state('schedule.n_v_bedroom_heating', 'on') }}
   ```
6. **VTherm** (type *Thermostat over climate*), named `N&V Bedroom`; then put its device
   in the bedroom area and give `climate.n_v_bedroom` the `heating` label:
   - *Main:* temperature sensor `sensor.n_v_bedroom_climate_sensor_temperature`, cycle
     10 min, use the central configuration and central mode.
   - *Underlyings:* `climate.n_v_bedroom_trv_left` and `climate.n_v_bedroom_trv_right`;
     self-regulation *Direct valve control*, regulation threshold **5** (a percentage in
     this mode; below 3 % the TRVZB can lose its calibration), minimum regulation period
     10 min.
   - *Valve regulation:* opening degree
     `number.n_v_bedroom_trv_left_valve_opening_degree`,
     `number.n_v_bedroom_trv_right_valve_opening_degree`; closing degree
     `number.n_v_bedroom_trv_left_valve_closing_degree`,
     `number.n_v_bedroom_trv_right_valve_closing_degree` (same order as the
     underlyings). VTherm sets the closing degree to 100 minus the opening, so the valve
     holds the computed position whatever the TRV's own sensor says.
   - *Features:* presence, with its own sensor `binary_sensor.n_v_bedroom_presence`
     (not the central one: it's specific to this room).
   - *Presets, TPI, Advanced:* from the central configuration.

   With comfort-away set to the eco temperature, comfort applies only while the
   presence sensor is on, so the preset automation below only has to handle the away
   toggle.
7. **Preset automation**, with the `heating` label:

   ```yaml
   alias: N&V Bedroom heating preset
   description: >-
     Eco while the away toggle is on (pre-heat overrides it), comfort otherwise.
     Versatile Thermostat applies comfort only while binary_sensor.n_v_bedroom_presence
     is on (home, pre-heat or schedule); otherwise its away temperature, which is set to
     eco.
   mode: restart
   triggers:
     # Reapply when automations are saved or reloaded
     - trigger: event
       event_type: automation_reloaded
     - trigger: state
       entity_id:
         - input_boolean.n_v_bedroom_away
         - input_boolean.n_v_bedroom_pre_heat
       to: null
     # Reapply after a Home Assistant restart
     - trigger: homeassistant
       event: start
   actions:
     - if:
         - condition: state
           entity_id: input_boolean.n_v_bedroom_away
           state: "on"
         - condition: state
           entity_id: input_boolean.n_v_bedroom_pre_heat
           state: "off"
       then:
         - action: climate.set_preset_mode
           target:
             entity_id: climate.n_v_bedroom
           data:
             preset_mode: eco
       else:
         - action: climate.set_preset_mode
           target:
             entity_id: climate.n_v_bedroom
           data:
             preset_mode: comfort
   ```

8. **Ending pre-heat**, without the `heating` label, so the toggle is also reset outside
   the heating season:

   ```yaml
   alias: N&V Bedroom pre-heat ends on arrival
   description: >-
     Pre-heat runs a 4-hour timer that survives restarts. It ends on arrival or when the
     timer finishes, whichever comes first.
   mode: queued
   triggers:
     # not_from: the toggle's state is restored at startup; that isn't a switch-on
     - trigger: state
       entity_id: input_boolean.n_v_bedroom_pre_heat
       to: "on"
       not_from: [unavailable, unknown]
       id: switched_on
     - trigger: state
       entity_id: input_boolean.n_v_bedroom_pre_heat
       to: "off"
       not_from: [unavailable, unknown]
       id: switched_off
     - trigger: timer.finished
       target:
         entity_id: timer.n_v_bedroom_pre_heat
       id: timer_finished
     - trigger: state
       entity_id: person.valentin_nemeth
       to: home
       id: arrived
     # A timer that ran out while Home Assistant was down may finish before this
     # automation listens; catch that here
     - trigger: homeassistant
       event: start
       id: started
   actions:
     - choose:
         - conditions:
             - condition: trigger
               id: switched_on
           sequence:
             - action: timer.start
               target:
                 entity_id: timer.n_v_bedroom_pre_heat
         - conditions:
             - condition: trigger
               id: switched_off
           sequence:
             - action: timer.cancel
               target:
                 entity_id: timer.n_v_bedroom_pre_heat
         - conditions:
             - condition: trigger
               id: started
             - condition: state
               entity_id: input_boolean.n_v_bedroom_pre_heat
               state: "on"
             - condition: state
               entity_id: timer.n_v_bedroom_pre_heat
               state: idle
           sequence:
             - action: input_boolean.turn_off
               target:
                 entity_id: input_boolean.n_v_bedroom_pre_heat
         - conditions:
             - condition: trigger
               id: [timer_finished, arrived]
             - condition: state
               entity_id: input_boolean.n_v_bedroom_pre_heat
               state: "on"
           sequence:
             - action: input_boolean.turn_off
               target:
                 entity_id: input_boolean.n_v_bedroom_pre_heat
   ```

9. **Status sensors**, for the dashboard: *Create helper → Template*, then the entity
   type.
   - *Binary sensor* `N&V Bedroom heating active`, device class *Heat*, on while any
     thermostat in the room is heating (the VTherm reports *heating* while its valves
     are open):
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

   How far VTherm opens the valves is `sensor.n_v_bedroom_valve_open_percent`. The
   TRVs' own *heating*/*idle* is unreliable in this mode, since their internal sensor
   doesn't drive the valve.

### Dashboard

The automatic Overview (areas and summaries) takes no custom cards, so the heating has its
own dashboard: *Settings → Dashboards → Add dashboard → New dashboard from scratch*,
`Heating`. Cards are added with the **＋** in a section; Tile cards for the toggles, the
comfort and eco preset temperatures and the status sensors, a Thermostat card for
`climate.n_v_bedroom` with the preset buttons, a Tile for the valve opening, and a
History graph of the room temperature, the target and *heating active*. Set
temperatures on the VTherm, not on the TRVs: VTherm overwrites the TRVs.

#### Climate chart

An apexcharts-card (from HACS), *N&V Bedroom climate*, shows how the bedroom's
temperature and humidity develop in correlation with the heating system's status, over the
last 24 hours. It's added as a new panel through the *Manual* (YAML) card
option. Swiping the chart scrolls to other timeframes; the toolbar zooms and pans.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: N&V Bedroom climate
  show_states: true
  colorize_states: true
graph_span: 24h
apex_config:
  chart:
    zoom:
      enabled: true
  xaxis:
    type: datetime
  toolbar:
    show: true
    tools:
      zoom: true
      zoomIn: true
      zoomOut: true
      pan: true
      reset: true
series:
  - entity: sensor.n_v_bedroom_climate_sensor_temperature
    name: Temperature
    unit: °C
    yaxis_id: default
    stroke_width: 2
    color: '#d32f2f'
  - entity: sensor.n_v_bedroom_climate_sensor_humidity
    name: Humidity
    unit: '%'
    yaxis_id: humidity
    stroke_width: 2
    color: '#03a9f4'
    stroke_dash: 5
  - entity: binary_sensor.n_v_bedroom_heating_active
    name: Heating Active
    type: area
    yaxis_id: heating
    transform: 'return x === ''on'' ? 1 : 0;'
    stroke_width: 0
    color: '#ff5722'
    opacity: 0.7
    curve: stepline
yaxis:
  - id: default
    apex_config:
      decimalsInFloat: 1
  - id: humidity
    opposite: true
    apex_config:
      min: 0
      max: 100
  # Heating shows as a band in the lower fifth (on = 1 of 0–5), behind the other lines
  - id: heating
    show: false
    min: 0
    max: 5
```

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
