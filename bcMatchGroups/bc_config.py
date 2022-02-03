from datetime import datetime
# Discord ID: Steam ID -- maybe handle multiple accounts?

# ###############################################################################


class bcConfig:

    # General
    DEBUG = True
    
    # REQUEST CONFIG SETTINGS
    search_count = 50
    visibility = 'public'
    # setting -- Alternative: 'by-distinct-players'
    team_identification = 'by-player-clusters'
    # setting -- Alternative 'by-name'
    player_identification = 'by-id'
    # sort_by = 'replay-date'                         # 'created
    sort_by = 'created'
    sort_dir = 'desc'                               # 'asc'

    # MATCH TYPE KEYWORDS

    REGULAR_SEASON_MT = "Regular Season"
    SCRIM_MT = "Scrims"
    PLAYOFF_MT = "Post-Season"
    POSTSEASON_MT = PLAYOFF_MT
    PRESEASON_MT = "Pre-Season"

    VALID_MATCH_TYPES = [REGULAR_SEASON_MT, SCRIM_MT, POSTSEASON_MT, PRESEASON_MT]

