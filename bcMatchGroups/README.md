# RLCogs: bcMatchGroups

The `bcMatchGroups` cog is responsible for managing teams and [ballchasing](https://ballchasing.com) replay groups for a franchise server. Once teams and groups are initially configured, bot commands can be used to create ballchasing replay groups, and view the performance of a team across the season, or the franchise across any given match night.

## Installation

The `bcMatchGroups` cog depends on the `accountManager` cog -- Install and load `accountManager` before installing `bcMatchGroups`

```
<p>cog install RLCogs bcMatchGroups
<p>load bcMatchGroups
```

Note: `<p>` represents the bot prefix.

<br>

---

<br>

## Establishing Franchise Teams

A role must exist in each server either in the format `<Team Name>`, or `<Team Name> (<tier>)`. Team roles _should_ be ordered in the permission tree from high to low in accordance with the tier hierarchy. This will impact how commands pertaining to all franchise teams are sorted.

To register one or more teams, the `<p>addTeamRoles` command must be used.

Examples:

```
?addTeamRoles Panthers
?addTeamRoles "Jaguars (Elite)" "Panters (Major)" "Ocelots (Minor)"
```

---

<br>

## Match Day Management

The Match Day (default: 1) can either be manually updated throughout the course of the season, or a bot owner or guild admin may set the dates for season matches, which will enable the bot to auto-update the match day as the season progresses.

### Manual Updates:

```
<p>setMatchDay <match day>
<p>nextMatchDay
```

`<p>nextMatchDay` increments the match day by 1

<br>

### Automatic Updates:

```
<p>setMatchDates [match dates...]
```

Registering match dates with the bot will enable automatic updates throughout the duration of the season. Match Dates must be provided in the a `month/date/year` format.

If the match day appears to be incorrect, the command `<p>updateMatchDay` should force the bot to update the current match day.

**Note: There is currently no way the bot can differentiate between the Preseason, Regular Season, Or Playoffs.**
<br>

---

<br>

## Team Group Setup

**Setup:**

```
<p>accountRegister steam <steam id>
<p>setMyBCAuthToken <ballchasing auth token>
<p>setSeasonGroup <group code>
```

Notes:

- When using `<p>accountRegister`, you must use the steam64 ID (i.e. `<p>accountRegister steam 76561198380344413`)
- You should only need to report your primary account. Teammates who play on steam should register their primary accounts as well as a backup.
- Non-steam accounts have minimal to no impact in this area.
- The ballchasing auth token is the same key as what you use for automatic uploads with BakkesMod, which can be found here: <https://ballchasing.com/upload>
- Your message will be deleted immediately after registering your auth key, so the information will remain as hidden as possible.
- `group_code` can be found from the link to the group.

For example:

- Link: <https://ballchasing.com/group/piranhas-regular-season-qbjds5aj1f>
- Code: **piranhas-regular-season-qbjds5aj1f**

<br>

---

<br>

## Regular Usage:

To have the bot create a replay group with the games from your recently played match, run the following command:

```
<p>bcr <opponent> [match day]
```

Notes:

- `bcr` is short for **ballchasing report**. This will automatically search for replays that your team played.
- If `opponent` is more than one word, you must put quotation marks around it. (i.e. `?bcr "Killer Whales"`)
- The `match_day` argument is optional, but the command might still find your old games if you didn't report on time. For context, it searches the past 20 private games you've played.
- Any member on the team who has registered an auth token can run this command

## Other Commands

- **Match Day Summary** (mds) - View results for your Franchise on the current match day
- **Get Season Performance** (gsp) - View results for your team

```
<p>mds [match day]
<p>gsp [team name]
```

Additional notes:

- To make an existing subgroup work correctly with this code, each match group must be written in the following format: **MD XX vs <opponent>**
- Brackets `[]` indicate optional parameters, while carrots `<>` indicate requred parameters

<br>

---
