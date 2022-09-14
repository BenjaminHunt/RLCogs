# Captains: Set Season Group (for a team)

Once teams are configured for the season, the team captains (captain role not required) can set up a ballchasing group for their current season.

Note: **ONLY** the top level group is required, (i.e. RSC S15 Gorillas)

<br>

# Overview

## GM/Server Owner Prerequisites
- Must have `accountManager` cog set up (**Note:** bot owner action)
- Must register a ballchasing upload token with the bot (`<p>help setGuildBCAuthToken`)
- Must register team roles with the bot (`<p>help setFranchiseTeams`, `<p>help clearFranchiseTeams`)
- At the end of a season, user `<p>endSeason` to clear all set team groups to prevent new subgroups being added to the previous season's group

## Player Prerequisites
- Must have a steam account registered with the bot (`<p>help registerAccount`)
- Must register your ballchasing upload token with the bot (`<p>setMyBCAuthToken`)
- Must upload ballchasing replays to this account

## Information Checks
- `<p>tokenCheck` checks if you have registered a valid ballchasing token
- `<p>getSeasonGroup` returns the top level ballchasing group for your team role

<br>

# Full Instructions

## 1. Register your ballchasing token with the bot.

Your token can be retrieved by signing into ballchasing.com with your steam account, and going to the uploads tab (top center), or by going to it directly by its url at https://ballchasing.com/upload.

![](https://media.discordapp.net/attachments/741758967260250213/1019695110826504242/unknown.png?width=2251&height=553)

- If you've generated a token before, click on the paper icon to the left of "Show."
- If you have not, click on the yellow refresh button to generate a new token.

When you have copied the token, you'll want to register it with the bot.

```
<p>setMyBCAuthToken <YOUR TOKEN>
```

## 2. Register your steam account with the bot.
You must register the same account you used to sign in and register an upload token. For the bot to work best, it is **strongly** encouraged to [enable automatic uploads](https://ballchasing.com/doc/faq#upload) with **BakkesMod**. Example:
        
    Format:
    <p>registerAccount <platform> <platform_id>

    Example:
    <p>registerAccount steam 76561198380344413

**Note:** If other players on your team will be uploading replays to ballchasing, encourage them to register their accounts as well. Your teammates may, but are not required to register an upload token.

## 3. Set your Top Level Group for the season

Once the pre-requisite steps (1-2) are done, group registration is very easy! All you need to do is create a ballchasing group for your team on the current season, and use `<p>setSeasonGroup` to save it to the bot.

<br>

1. **Create ballchasing group**

    a. Under `Replay Groups` click on `My replay Groups`
    ![](https://cdn.discordapp.com/attachments/741758967260250213/1019698623174422628/unknown.png)

    b. **[Option 1]** Scroll down and click `Create New Group`
    ![](https://cdn.discordapp.com/attachments/741758967260250213/1019699256958918708/unknown.png)

    **[Option 2]** If you want your ballchasing group to be in another subgroup, you may navigate to that point and make the subgroup there by clicking `New Group`.
    ![](https://media.discordapp.net/attachments/741758967260250213/1019700329207574729/unknown.png)

    c. Give your group a name, and set the configurations to align with the screenshot below:
    ![](https://cdn.discordapp.com/attachments/741758967260250213/1019699889791316118/unknown.png)

<br>

2. **Get the link or group ID from your new group.**

    a. Navigate to your new season ballchasing group
    ![](https://cdn.discordapp.com/attachments/741758967260250213/1019701372314198067/unknown.png)

    In this example, you can see the url is `https://ballchasing.com/group/s15-gorillas-oj7jeak7kq`. The ballchasing group code is everything that follows `group/`. So in this example, the group code is `s15-gorillas-oj7jeak7kq`. Either value can be used when using the following command to set the season group.

<br>

3. **Register the Team Ballchasing Group for the season**

    As stated previously, either the link or the group code can be used to register the season group

    - Link: `https://ballchasing.com/group/s15-gorillas-oj7jeak7kq`
    - Group: `s15-gorillas-oj7jeak7kq`

    Use `<p>setSeasonGroup <link or code>` to register your group

    ```
    <p>setSeasonGroup https://ballchasing.com/group/s15-gorillas-oj7jeak7kq

    OR

    <p>setSeasonGroup s15-gorillas-oj7jeak7kq
    ```

<br>

## That's it! You should be all set now! If you have any further questions, please ask your GM or contact nullidea#3117 on discord.

