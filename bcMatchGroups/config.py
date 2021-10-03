from datetime import datetime
# Discord ID: Steam ID -- maybe handle multiple accounts?

# ###############################################################################


class config:
    search_count = 50
    visibility = 'public'
    # setting -- Alternative: 'by-distinct-players'
    team_identification = 'by-player-clusters'
    # setting -- Alternative 'by-name'
    player_identification = 'by-id'
    sort_by = 'replay-date'                         # 'created
    sort_dir = 'desc'                               # 'asc'
