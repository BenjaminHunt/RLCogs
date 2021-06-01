# RLCogs
Redbot Cogs for Rocket League:

RLCogs is a collection of cogs written in Python that can be installed and used with the [Red Discord Bot](https://docs.discord.red/en/stable/index.html). These cogs are primarily written for franchises within [RSC (Rocket Soccar Confederation)](https://www.rocketsoccarconfederation.com/), a 3v3 Rocket League Amateur League that runs through [Discord](https://discord.gg/rsc).

## Installation

Follow the Red Discord Bot installation guide for [Windows](https://docs.discord.red/en/stable/install_windows.html) or [Linux/Mac](https://docs.discord.red/en/stable/install_linux_mac.html). You'll need to also [create a Discord bot account](https://discordpy.readthedocs.io/en/latest/discord.html) to get a token for use during the bot setup. After you have the bot setup, running, and invited to one of your Discord servers, you can begin installing and loading the cogs to the bot using the following commands in Discord (where `<p>` represents the prefix you selected your bot to use):

```
<p>load downloader
<p>repo add RLCogs https://github.com/adammast/RSCBot [branch]
<p>cog install RLCogs <cog_name>
<p>load <cog_name>
```

## Available Cogs

### accountManager
Stores account information for Rocket League accounts for discord members. Other cogs may depend on this cog for core functionality.

### bcMatchGroups
Helps RSC franchises manage their team's [ballchasing](https://ballchasing.com) replay groups, between group creation and acessing information such as franchise or team performance across a given match day or season.
