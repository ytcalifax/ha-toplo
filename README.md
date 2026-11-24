# 🔥 Toplo.bg for Home Assistant

> **Monitor your Toplo.bg account, invoices, and district heating use from Home Assistant.**

Toplo.bg brings account and installation data into Home Assistant. Track recent invoices, monthly heating and hot water consumption, station readings, and annual alignment figures. Sign in through the integration setup form; no credentials belong in YAML or source files.

## ✨ Features

- **🧾 Invoice monitoring**: See the latest invoice total, outstanding amount, and returned invoice history.
- **♨️ Heating and hot water**: Track the latest monthly consumption and view the returned monthly records.
- **🏢 Station readings**: Monitor heating and hot water use reported for the building's station.
- **📊 Annual alignment**: See annual final heating and hot water amounts with the API's alignment periods.
- **👤 Account and locations**: View your Toplo.bg profile and one Home Assistant device per installation.
- **✏️ Owner name override**: Set a custom owner label during setup when the account holder differs from the location owner.
- **🔄 Automatic updates**: Refresh data hourly and add entities when new installations appear.
- **🇧🇬 Bulgarian and English**: The setup flow and sensor names follow the selected Home Assistant language.

## 🚀 Quick Start

[![Open Toplo.bg in the Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=ytcalifax&repository=ha-toplo&category=integration)

### Install with HACS

Use the button above to open Toplo.bg in the Home Assistant Marketplace. HACS will add the repository; install the integration there, then restart Home Assistant.

1. In HACS, open **Integrations → ⋮ → Custom repositories**.
2. Enter the GitHub repository URL and select **Integration**.
3. Install **Toplo.bg** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and choose **Toplo.bg**.

### Manual installation

1. Copy `custom_components/toplo_bg` into the Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add **Toplo.bg** from **Settings → Devices & services**.

## 🔐 Setup

Enter your Toplo.bg email and password in the setup form. Home Assistant stores them in the config entry. The integration sends them to `https://api.toplo.bg` over HTTPS to sign in and refresh the account data. If credentials stop working, Home Assistant opens a reauthentication form.

The optional **Location owner override** replaces the owner label on installation devices. Leave it blank to use the owner returned by Toplo.bg.

## 📡 Entities

Each installation creates these sensors:

| Sensor | Unit | Data |
|---|---|---|
| Latest invoice total | EUR | Most recent invoice total; invoice records in attributes |
| Invoice due | EUR | Outstanding amount on the most recent invoice |
| Heating consumption | Gcal | Latest monthly reading; monthly history in attributes |
| Hot water consumption | Gcal | Latest monthly reading; monthly history in attributes |
| Station heating consumption | kWh | Latest station reading; station history in attributes |
| Station hot water consumption | kWh | Latest station reading; station history in attributes |
| Annual aligned heating | Gcal | Sum of annual final heating amounts; alignment records in attributes |
| Annual aligned hot water | Gcal | Sum of annual final hot water amounts; alignment records in attributes |

A separate account sensor exposes the profile fields returned by Toplo.bg. When an installation is removed from the account, its existing entities become unavailable. Toplo.bg data is cloud-provided, so Home Assistant needs internet access to update it.

## 🧰 Data and privacy

The integration calls Toplo.bg's login, profile, installations, invoices, monthly consumption, station consumption, and annual alignment endpoints. Updates run hourly. Profile details, including contact information returned by the API, are available on the account sensor; installation and billing details are available on their related sensors. Data stays in Home Assistant's recorder according to your recorder settings.

This is a community integration and is not affiliated with Toplo.bg or Home Assistant.

## 🛠️ Troubleshooting

- **Invalid credentials**: Complete the reauthentication form from **Settings → Devices & services**.
- **Entities unavailable**: Check Home Assistant's internet access and the integration logs. Temporary API failures recover on a later update.
- **No installation entities**: Confirm that the Toplo.bg account has at least one active installation.
