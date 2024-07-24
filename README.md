<div align="center">

<img src="./assets/plutus_icon_full.png" height="400px" alt="Plutus Terminal Splash Screen"/>

# Plutus Terminal
</div>

## What is Plutus Terminal? 🌟

<p align="center">
    <img src="./assets/plutus_splash.gif" alt="Plutus Terminal Splash Screen"/>
</p>

Plutus Terminal is a powerful **open-source** crypto news trading terminal with the
focus on Perpetuals DEX.

Designed to be user-friendly and easy to use.
It allows you to trade using real-time news updates, control positions and manage
multiple DEX's.

Plutus terminal embraces web3 mentality, your are awalys in contorl of your keys,
it also handles everything locally and interact directly with the DEX contracts.

## Features 🎯

* 💻 Runs locally on your computer
* 🌐 Cross-platform (Windows, Linux, MacOS)
* 🔄 Intregates TreeOfAlpha and PhoenixNews
* 🛠️  News filters highly customizable
* 🔔 Never miss a news with desktop notifications
* 💎 Open-source and free
* 🌍 Use your own RPC nodes

## ⚠️  Disclaimer

Plutus Terminal is an **alpha** version. It is not ready for production use.

Plutus terminal will trade on the Perpetuals DEX using real money. Do not risk money
which you are afraid to lose.

**PLUTUS-TERMINAL IS PROVIDED "AS IS". USE THE SOFTWARE AT YOUR OWN RISK.** THE AUTHORS
AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS. THE
ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH YOU.
SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY
SERVICING, REPAIR OR CORRECTION.

Everyone is encouraged to read the source code and understand the code before using it.

Positions open with Plutus Terminal will automatically use our referral
codes when possible.

## 🛠️  Installation

Plutus terminal is a python package and depends on multiple modules.
You can install it downloading the PyApp excutable, from pipx or build it using poetry.

<details>
<summary>
<strong>Installation using <code>PyApp</code>:</strong>
</summary>
<br>
#TODO

</details>

<br>

<details>
<summary>
<strong>Installation using <code>pipx</code>:</strong>
</summary>
<br>

Install plutus-terminal with:

```bash
pipx install --pip-args='--pre' plutus-terminal
```

Run the tool with:

```bash
plutus-terminal
```

</details>

<br>

<details>
<summary>
<strong>Installation using <code>Poetry</code>:</strong>
</summary>
<br>

First, clone the repository:

```bash
git clone https://github.com/plutus-terminal/plutus-terminal.git
```

Navigate to the cloned repository:

```bash
cd plutus-terminal
```

Then, install the package:

```bash
poetry install
```

Run the tool with:

```bash
poetry run plutus-terminal
```

</details>

## 🚀 Quick Start

Bellow you will find a simple guide on how to get started with Plutus Terminal.
For a more complete documentation please refer to the
[documentation](https://github.com/plutus-terminal/plutus-terminal/blob/main/README.md)

### Create new account

When opening the terminal the first time, you will be prompted to create an account.
<details>
<summary>
See image...
</summary>
<div align="center">
<img src="./assets/create_new_acc.png" alt="Create Account"/>
</div>
<br>
> [!NOTE]
> The same private key can be used to create multiple accounts on different
> exchanges.
</details>
<br>

Fill the form with the required information and press `Create New Account`.

> [!CAUTION]
> The private key will be stored in the OS keyring, always ensure
> your OS is secure.

### News quick market buy

Once the account is created you should see the terminal opening after a couple
of seconds.

News will be presented in real-time under the `News Feed` widget, if the coins
associated with the news are available on the selected exchange you will see a
quick trade group appear on the news.

<details>
<summary>
See image...
</summary>
<br>
<div align="center">
<img src="./assets/news_example.png" alt="News with quick buy trades."/>
</div>
</details>
<br>

> [!NOTE]
> `Quick Market Buy` values represent the amount of capital that will be used
> to open your position. This value get's multiplied by the current pair
> leverage to determine the size of the position.

### Auto TP/SL

Quick Market buys can be configured with `TP` and `SL` values. For that you
will need to open the configuration window by pressing the gear icon on the top
right corner.

Once the window is open, you can set the `TP` and `SL` values on the `Trade` tab.

<details>
<summary>
See image...
</summary>
<br>
<div align="center">
<img src="./assets/auto_tp_sl_config.gif" alt="Auto TP/SL"/>
</div>
</details>
<br>

> [!NOTE]
> Each account have their own `TP` and `SL` values

### News Filters

You can configure the news filters by clicking on the `Filters` tab in the
configuration window.

There are 2 types of filters `Keyword Matching` and `Data Matching`. Both of
them allow actions to happen when the conditions are meet.

Posible actions are:

| Action            | Description                  |
| ----------------- | ---------------------------- |
| Sound Association | Play a specific sound        |
| Coin Association  | Associate a coin to the news |
| Ignore News       | Don't display the news       |

#### Keyword Matching

The `Keyword Matching` filter allows you to filter specific keywords in the
news body if the keyword is present the selected action will run on the news.

<details>
<summary>
Example
</summary>
<br>
<div align="center">
<img src="./assets/keyword_matching.png" alt="Keyword Matching"/>
</div>
This filter will play the `pause` sound if the word `Foxify` is present in the
news body and it will color that word dark pink.
</details>


#### Data Matching

The `Data Matching` filter allows you to filter for word on specific data
fields if the word is present in the specified datafield then the selected
action will run on the news.

<details>
<summary>
Example
</summary>
<br>
<div align="center">
<img src="./assets/data_matching.png" alt="Data Matching"/>
</div>
This filter will play the `powerup` sound if the title of the news is `Tree News (@News_Of_Alpha)`
</details>
<br>


> [!NOTE]
> Filters will only be saved if the `Save Filters` button is pressed and
> will only be applied after a restart.

#### Hotkey Shortcuts

| Hotkey             | Action                                                         |
| ------------------ | -------------------------------------------------------------  |
| `w`                | Move selected new 1 up                                         |
| `s`                | Move selected new 1 down                                       |
| `q`                | Move selected to the top                                       |
| `\`                | Open token modal search                                        |
| `Ctrl+j` or `UP`   | (Only on modal search) Move modal auto complete selection down |
| `Ctrl+k` or `DOWN` | (Only on modal search) Move modal auto complete selection down |



## 🌐 Exchanges

Current supported exchanges are:

* <img src="./assets/foxify.svg" height="25px" alt="Foxify Logo"/> [Foxify](https://perp.foxify.trade/#/trade/?ref=plutus_terminal)

Planned support:

* <img src="./assets/foxify.svg" height="25px" alt="Foxify Logo"/> [Foxify FUNDED](https://foxify-1.gitbook.io/foxify-funded-litepaper)
* <img src="./assets/gmx.svg" height="25px" alt="Foxify Logo"/> [GMX](https://app.gmx.io/#/trade/?ref=plutus_terminal)

## ❤️  Support

If this project was helpful, please consider supporting by:

* ⭐[Starring the project on GitHub](https://github.com/plutus-terminal/plutus-terminal)
* Use referral code `plutus_terminal`
* Make a donation:
    * EVM ADDRESS: 0x92E3E69597A81c9D8F131FD590E8028aD16d1155

Every bit helps. Thank you!

## 📜 License

Plutus Terminal is licensed under the `GNU General Public License version 3.0`

See [LICENSE](./LICENSE) for details.
