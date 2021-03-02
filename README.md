# RSCBot: combineRooms

The `bcSixMans` cog is primarily responsible for saving sixMans games to a replay group on [ballchasing.com](https://ballchasing.com/). When a Six Mans series is completed, and a score is reported, the cog searches for the replays on ballchasing and saves them to the designated replay group.

## Installation

The `bcSixMans` cog depends on the [`sixMans` cog](https://github.com/adammast/RSCBot/tree/master/sixMans) in the [RSCBot codebase](https://github.com/adammast/RSCBot). Install and configure `sixMans` before installing this cog.

```
<p>cog install RLCogs bcSixMans
<p>load bcSixMans
```

## Usage

- `<p>setAuthToken`
  - Sets the Auth Key for Ballchasing API requests.
  - Note: Auth Token must be generated from the Ballchasing group owner

---

## Customization

TODO: Remove this vv

- `<p>setRoomCapacity` (Default: 10)
  - Sets the limit for discord members in room.

## Other commands

The following commands can be used to check current properties of the server:

- `<p>getRoomCapacity`
- `<p>getCombinePublicity`
- `<p>getAcronym`
