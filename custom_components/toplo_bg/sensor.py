"""Sensors for Toplo.bg installations."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import ToploConfigEntry
from .const import CONF_OWNER

SENSORS = (
    SensorEntityDescription(
        key="latest_invoice",
        translation_key="latest_invoice",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:file-document-outline",
    ),
    SensorEntityDescription(
        key="invoice_due",
        translation_key="invoice_due",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:cash-clock",
    ),
    SensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="hot_water",
        translation_key="hot_water",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        icon="mdi:water-thermometer",
    ),
    SensorEntityDescription(
        key="station_heating",
        translation_key="station_heating",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="station_hot_water",
        translation_key="station_hot_water",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        icon="mdi:water-thermometer",
    ),
    SensorEntityDescription(
        key="aligning_heating",
        translation_key="aligning_heating",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        icon="mdi:scale-balance",
    ),
    SensorEntityDescription(
        key="aligning_hot_water",
        translation_key="aligning_hot_water",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        icon="mdi:scale-balance",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ToploConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add entities for current and newly discovered installations."""
    coordinator = entry.runtime_data
    known_ids: set[str] = set()

    @callback
    def add_installations() -> None:
        new_entities = []
        for installation in coordinator.data["installations"]:
            installation_id = installation["id"]
            if installation_id in known_ids:
                continue
            known_ids.add(installation_id)
            new_entities.extend(
                ToploSensor(coordinator, entry, installation_id, description)
                for description in SENSORS
            )
        if new_entities:
            async_add_entities(new_entities)

    add_installations()
    async_add_entities([ToploAccountSensor(coordinator, entry)])
    entry.async_on_unload(coordinator.async_add_listener(add_installations))


class ToploAccountSensor(CoordinatorEntity, SensorEntity):
    """Expose the Toplo.bg profile once, separately from installation sensors."""

    _attr_has_entity_name = True
    _attr_translation_key = "account"
    _attr_icon = "mdi:account"

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ToploConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_account"
        self._attr_device_info = {
            "identifiers": {("toplo_bg", f"account_{entry.entry_id}")},
            "name": "Toplo.bg account",
            "manufacturer": "Toplo.bg",
        }

    @property
    def native_value(self):
        """Return the account profile name."""
        return self.coordinator.data["profile"].get("name")

    @property
    def extra_state_attributes(self) -> dict:
        """Return profile details available from the API."""
        return self.coordinator.data["profile"]


class ToploSensor(CoordinatorEntity, SensorEntity):
    """Represent one value for a Toplo.bg installation."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ToploConfigEntry,
        installation_id: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._installation_id = installation_id
        self._owner = entry.data.get(CONF_OWNER, "")
        self._attr_unique_id = f"{installation_id}_{description.key}"
        installation = self._installation
        owner = self._owner or installation.get("owner")
        installation_number = installation.get("number")
        self._attr_device_info = {
            "identifiers": {("toplo_bg", installation_id)},
            "name": (
                f"{owner} ({installation_number})"
                if owner and installation_number
                else owner or installation.get("name") or f"Installation {installation_id}"
            ),
            "manufacturer": "Toplo.bg",
            "model": str(installation_number or "Unknown"),
        }

    @property
    def available(self) -> bool:
        """Mark removed installations unavailable instead of raising."""
        return super().available and self._installation is not None

    @property
    def _installation(self) -> dict | None:
        return next(
            (
                item
                for item in self.coordinator.data["installations"]
                if item["id"] == self._installation_id
            ),
            None,
        )

    @property
    def native_value(self):
        """Return the latest value for this sensor."""
        item = self._installation
        if item is None:
            return None
        key = self.entity_description.key
        if key in ("latest_invoice", "invoice_due"):
            invoices = item["invoices"]
            if not invoices:
                return None
            latest = max(invoices, key=lambda invoice: invoice.get("documentDate", ""))
            return latest.get("total" if key == "latest_invoice" else "due")
        if key in ("heating", "hot_water", "station_heating", "station_hot_water"):
            source = item["station" if key.startswith("station_") else "consumption"]
            if not source:
                return None
            latest = max(source, key=lambda row: (row.get("year", 0), row.get("month", 0)))
            metric = "heatingEnergy" if key.endswith("heating") else "hotWaterEnergy"
            return latest.get(metric)
        metric = "heatingEnergyFinal" if key == "aligning_heating" else "hotWaterEnergyFinal"
        values = item["aligning"]
        return sum((value.get(metric) or 0) for value in values) if values else None

    @property
    def extra_state_attributes(self) -> dict:
        """Expose relevant account data once per sensor category, without profile PII."""
        item = self._installation
        if item is None:
            return {}
        attributes = {
            "owner": self._owner or item.get("owner"),
            "installation_number": item.get("number"),
            "installation_address": item.get("address"),
        }
        key = self.entity_description.key
        if key in ("latest_invoice", "invoice_due"):
            attributes["invoices"] = item["invoices"]
        elif key in ("heating", "hot_water"):
            attributes["monthly_consumption"] = item["consumption"]
            if item["consumption"]:
                latest = max(
                    item["consumption"],
                    key=lambda row: (row.get("year", 0), row.get("month", 0)),
                )
                attributes["reading_period"] = f"{latest.get('year')}-{latest.get('month'):02}"
        elif key.startswith("station_"):
            attributes["station_consumption"] = item["station"]
            if item["station"]:
                latest = max(
                    item["station"], key=lambda row: (row.get("year", 0), row.get("month", 0))
                )
                attributes["reading_period"] = f"{latest.get('year')}-{latest.get('month'):02}"
        else:
            attributes["annual_aligning"] = item["aligning"]
        return attributes
