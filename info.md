## App configuration

```yaml
catrack:
  module: catrack
  class: CaTrack
  cat_name: Shiva
  delay: 20
  movement_threshold: 15
  notify_service: notify.muh
  cat_flap_sensors: [sensor.shiva_status]
  vibration_sensors: [sensor.coordination_gardenlounge, sensor.bed_activity_gardenlounge]
  person_sensors: [group.devices_muh]
```

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | catrack | The module name of the app.
`class` | False | string | CaTrack | The name of the Class.
`cat_name` | False | string |  | TODO
`delay` | True | string |  | TODO
`movement_threshold` | True | string |  | TODO
`notify_service` | True | string |  | TODO
`cat_flap_sensors` | True | string |  | TODO
`vibration_sensors` | True | string |  | TODO
`person_sensors` | True | string |  | TODO
