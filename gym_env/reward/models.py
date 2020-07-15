class ActionData:
    """Data at the time of performing an action"""

    def __init__(self,
                 player_stack, player_pot, round_pot, community_pot):
        """data"""
        self.player_stack = player_stack
        self.player_pot = player_pot
        self.round_pot = round_pot
        self.community_pot = community_pot
