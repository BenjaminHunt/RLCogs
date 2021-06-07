from datetime import datetime
# Discord ID: Steam ID -- maybe handle multiple accounts?

# ###############################################################################

class config:
    search_count = 20
    visibility = 'public'
    team_identification = 'by-distinct-players'     # setting -- Alternative: 'by-player-clusters'
    player_identification = 'by-id'                 # setting -- Alternative 'by-name'
    sort_by = 'replay-date'                         # 'created
    sort_dir = 'desc'                               # 'asc'