# RLCogs: accountManager

It is responsible for managing Rocket League accounts registered to discord members. Auth Tokens are stored on a per-guild basis, but accounts are saved without a direct association to a guild.

## Requirements

- Python `requests` package

## Installation/Setup

The `accountManager` cog has no discord cog dependencies. To install and load the cogs, run the following bot commands:

```
<p>cog install RLCogs bcMatchGroups
<p>load bcMatchGroups
```

Note: `<p>` represents the bot prefix.

<br>

A **Ballchasing** (BC) authentication token or "Upload Key" must be registered with the bot to enable accounts to be added and removed. After logging into [ballchasing](https://ballchasing.com), you may obtain a ballchasing token [here](https://ballchasing.com/upload).

### Example:

`<p>registerAccount steam 76561198380344413`

<br>

---

## _Admin Commands_

### Register Ballchasing Token

- `<p>setGuildBCAuthToken <auth token>`

---

<br>

## _Member Commands_

### Add Account

- `<p>registerAccount <platform> <identifier>`

### View Accounts

- `<p>accounts` - lists accounts as hard-coded ballchasing IDs
- `<p>bcPages` - Links to ballchasing profiles for registered accounts

### Remove Accounts

- `<p>unregisterAccount <platform> [identifier]` - removes one or more accounts based on what parameters are specified
- `<p>unregisterAccounts` - removes all accounts

<br>

---

<br>

## More Help:

Command documentation can be found with the bot using the help command: `<p>help <command name>`
