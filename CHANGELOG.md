# Changelog

## 0.1.0b6 - 19/12/2024

* [feat] Improve charting tools (#55)
* [fix] Fix partial closes and decrease orders (#56)

## 0.1.0b5 - 09/12/2024

* [fix] Fix TreeNews keyError on news process (#68)

## 0.1.0b4 - 25/11/2024

* [feat] Improve news formatting and UI (#62)
* [feat] Include timezone configurations. (#64)

## 0.1.0b3 - 10/11/2024

* [doc] Update README with FoxifyFunded support
* [fix] Calculate min and max order for foxify based on starting capital (#49)
* [Fix] Reset current pair to default pair (#53)
* [refactor] Change logs directory and add log viewer on settings (#57)
* [feat] Preserve current pair when changing accounts if available (#58)

## 0.1.0b2 - 04/09/2024

* [fix] Filter can be updated without a full restart (#14)
* [fix] Getting correct min and max order size for Foxify Funded. (#20)
* [fix] Change leverage spinBox signal to editingFinished (#21)
* [feat] Preserve current timeframe when changing account (#23)
* [fix] Fix Foxify Funded order size for Challenge level (#26)
* [feat] Add configuration for popup location and change the default to bottom left (#31)
* [fix] Fix Est. Liq values not updating after account change (#32)
* [fix] Fix un-subscription from FOXIFY fetcher (#37)
* [feat] Add password encryption when storing sensitive data (#38)
* [Feat] Add CI/DI (#42)
* [refactor] Remove code related CEX

## 0.1.0a2 - 29/07/2024

* [docs] Update disclaimer
* [fix] Fix position fee argument
* [fix] Remove min and max when managing orders
* [feat] [Foxify] Fix liquidation calculation
* [fix] Ensure cycle_provider is thread safe.
* [fix] Include poetry.lock
* [fix]Fix chart price and time scale

## 0.1.0a1 - 29/07/2024

* [feat] Improved starting performance
* [feat] Added button to approve contracts
* [feat] Added positions/order lines to chart
* [feat] Added liquidation info on positions table
* [feat] Add validation check when opening positions
* [fix] [Foxify] Fix liquidation to match
* [fix] [Foxify] Added multiple RPCs to fetcher
* [feat] [Foxify FUNDED] Added Funded
* [feat] Added dynamic info on account info

## 0.1.0a0 - 24/07/2024

* Initial Public unstable release
