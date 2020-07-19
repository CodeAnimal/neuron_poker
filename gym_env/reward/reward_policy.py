"""Reward Policy"""

import logging
from gym_env.env import Action
log = logging.getLogger(__name__)


class RewardPolicy:
    """Abstract base class for all implemented reward policies.

    Each policy helps with calculating the reward after an action on the environment.

    Do not use this abstract base class directly but instead use one of the concrete policies implemented.
    To implement your own policy, you have to implement the following methods:

    - `calculate_reward`

    # Arguments
        env (gym_env.env.HoldemTable): Poker environment
        winning_agent (int): The index of the winning agent. Can be None (not done so unknown)
        acting_agent_idx (int): The index of the originally acting agent.
        last_action (gym_env.env.Action): The last action taken by the acting agent
    """

    def calculate_reward(self, **kwargs):
        raise NotImplementedError()


class BasicRewardPolicy(RewardPolicy):
    """Preliminiary implementation of reward function

    - Currently missing potential additional winnings from future contributions"""

    def calculate_reward(self, env, last_action, winning_agent, acting_agent_idx, action_data):
        # if last_action == Action.FOLD:
        #     self.reward = -(
        #             self.community_pot + self.current_round_pot)
        # else:
        #     self.reward = self.player_data.equity_to_river_alive * (self.community_pot + self.current_round_pot) - \
        #                   (1 - self.player_data.equity_to_river_alive) * self.player_pots[self.current_player.seat]
        reward = 0

        _ = last_action
        if env.done:
            won = 1 if winning_agent == acting_agent_idx else -1

            reward = env.initial_stacks * len(env.players) * won

        elif len(env.funds_history) > 1:
            reward = env.funds_history.iloc[-1, acting_agent_idx] - env.funds_history.iloc[
                -2, acting_agent_idx]

        log.debug(f"Calculated reward: {reward}")
        return reward
