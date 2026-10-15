from typing import Literal

ActionCode = Literal["inspect_drainage", "inspect_crop", "monitor_heat", "request_field_visit", "plant_crop", "hold_planting"]
ACTIONS = {
    "inspect_drainage": "Inspect the plot's drainage and record any standing water for officer review.",
    "inspect_crop": "Inspect the crop and record visible symptoms for officer review.",
    "monitor_heat": "Observe the crop for signs of heat stress and report observations to the extension officer.",
    "request_field_visit": "Arrange a field inspection with the extension officer before taking further action.",
    "plant_crop": "Plant the recorded crop within the reviewed planting window after the officer confirms field readiness.",
    "hold_planting": "Hold planting and ask the extension officer to reassess when the forecast or field conditions change.",
}
