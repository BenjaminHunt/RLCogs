# RLCogs

## Requirements

- Python `requests` package

## Installation/Setup

The `accountManager` cog has no discord cog dependencies.

```
<p>cog install RLCogs bcMatchGroups
<p>load bcMatchGroups
```

<br>

A **Ballchasing** (BC) authentication token or "Upload Key" must be registered with the bot to enable accounts to be added and removed. After logging into [ballchasing](https://ballchasing.com), you may obtain a ballchasing token [here](https://ballchasing.com/upload).

A **Tracker Network** (TRN) authentication token or "API Key" is not required, but enables some improvements with the bot, such as registering accounts by their id name, rather than their id code. After logging into [The Tracker Network](https://tracker.gg), you may obtain a TRN Auth Token by **creating a project** in the [Developer Portal](https://tracker.gg/developers).

### Example:

- Without TRN Token: `<p>registerAccount steam 76561198380344413`
- With TRN Token: `<p>registerAccount steam nullidea`

<br>

---

## _Admin Commands_

Note: `<p>` represents the bot prefix.

### Register Ballchasing Token

- `<p>setGuildBCAuthToken <auth token>`

### Register Tracker-Network Token

- `<p>setTRNAuthToken <auth token>`
  <br>

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
