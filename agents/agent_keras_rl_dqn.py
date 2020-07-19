"""Player based on a trained neural network"""
# pylint: disable=wrong-import-order
import logging
import time

import numpy as np

from gym_env.env import Action

import tensorflow as tf
from tensorflow.python.framework.ops import disable_eager_execution
import json
import pickle

from tensorflow.keras.models import Sequential, model_from_json
from tensorflow.keras.callbacks import TensorBoard
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import Adam

from rl.policy import BoltzmannQPolicy
from rl.memory import SequentialMemory
from rl.agents import DQNAgent
from rl.core import Processor

autoplay = True  # play automatically if played against keras-rl

window_length = 1
nb_max_start_steps = 1  # random action
train_interval = 100  # train every 100 steps
nb_steps_warmup = 50  # before training starts, should be higher than start steps
nb_steps = 1e5
memory_limit = int(nb_steps / 2)
batch_size = 500  # items sampled from memory to train
enable_double_dqn = False

log = logging.getLogger(__name__)


class Player:
    """Mandatory class with the player methods"""

    def __init__(self, name='DQN', load_model=None, env=None):
        """Initiaization of an agent"""
        self.equity_alive = 0
        self.actions = []
        self.last_action_in_stage = ''
        self.temp_stack = []
        self.name = name
        self.autoplay = True
        self.equity_player = True

        self.dqn = None
        self.memory = None
        self.model = None
        self.env = env

        if load_model:
            self.load(load_model)

    def initiate_agent(self, env):
        """initiate a deep Q agent"""
        tf.compat.v1.disable_eager_execution()
        disable_eager_execution()

        env.reset()
        self.env = env

        nb_actions = self.env.action_space.n

        self.model = Sequential()
        self.model.add(Dense(512, activation='relu', input_shape=env.observation_space))
        self.model.add(Dropout(0.2))
        self.model.add(Dense(512, activation='relu'))
        self.model.add(Dropout(0.2))
        self.model.add(Dense(512, activation='relu'))
        self.model.add(Dropout(0.2))
        self.model.add(Dense(nb_actions, activation='linear'))

        # Finally, we configure and compile our agent. You can use every built-in Keras optimizer and
        # even the metrics!
        self.memory = SequentialMemory(limit=memory_limit, window_length=window_length)
        policy = TrumpPolicy()

        nb_actions = env.action_space.n

        self.dqn = DQNAgent(model=self.model, nb_actions=nb_actions, memory=self.memory, nb_steps_warmup=nb_steps_warmup,
                            target_model_update=1e-2, policy=policy,
                            processor=CustomTrainProcessor(),
                            batch_size=batch_size, train_interval=train_interval, enable_double_dqn=enable_double_dqn)
        self.dqn.compile(Adam(lr=1e-3), metrics=['mae'])

    def start_step_policy(self, observation):
        """Custom policy for random decisions for warm up."""
        log.info("Random action")
        _ = observation
        action = self.env.action_space.sample()
        return action

    def train(self, env_name, steps=nb_steps):
        """Train a model"""
        # initiate training loop
        timestr = time.strftime("%Y%m%d-%H%M%S") + "_" + str(env_name)
        tensorboard = TensorBoard(log_dir='./Graph/{}'.format(timestr), histogram_freq=0, write_graph=True,
                                  write_images=False)

        self.dqn.fit(self.env, nb_max_start_steps=nb_max_start_steps, nb_steps=steps, visualize=False, verbose=2,
                     start_step_policy=self.start_step_policy, callbacks=[tensorboard])
        log.info("###################################################################################################")
        log.info("###################################################################################################")
        log.info(f"Training finished after {steps} steps")

        # Save the architecture
        dqn_json = self.model.to_json()
        with open("dqn_{}_json.json".format(env_name), "w") as json_file:
            json.dump(dqn_json, json_file)
        log.info(f"Model saved to 'dqn_{env_name}_json.json'")

        # After training is done, we save the final weights.
        self.dqn.save_weights('dqn_{}_weights.h5'.format(env_name), overwrite=True)
        log.info(f"Weights saved to 'dqn_{env_name}_weights.h5'")

        mem = (self.memory,
               self.memory.actions,
               self.memory.rewards,
               self.memory.terminals,
               self.memory.observations)
        pickle.dump(mem, open("dqn_{}_memory.pkl".format(env_name), "wb"), protocol=-1)
        log.info(f"Sequential memory saved to 'dqn_{env_name}_memory.pkl'")

        log.info(f"Running test for 5 episodes'")
        # Finally, evaluate our algorithm for 5 episodes.
        self.dqn.test(self.env, nb_episodes=5, visualize=False)

    def load(self, env_name):
        """Load a model"""

        # Load the architecture
        with open('dqn_{}_json.json'.format(env_name), 'r') as architecture_json:
            dqn_json = json.load(architecture_json)

        self.model = model_from_json(dqn_json)
        self.model.load_weights('dqn_{}_weights.h5'.format(env_name))

        (self.memory, self.memory.actions,
         self.memory.rewards,
         self.memory.terminals,
         self.memory.observations) = pickle.load(open("dqn_{}_memory.pkl".format(env_name), "rb"))

    def play(self, nb_episodes=5, render=False):
        """Let the agent play"""
        self.memory = SequentialMemory(limit=memory_limit, window_length=window_length)
        policy = TrumpPolicy()

        class CustomPlayProcessor(Processor):  # pylint: disable=redefined-outer-name
            """The agent and the environment"""

            def process_state_batch(self, batch):
                """
                Given a state batch, I want to remove the second dimension, because it's
                useless and prevents me from feeding the tensor into my CNN
                """
                return np.squeeze(batch, axis=1)

            def process_info(self, info):
                processed_info = info['player_data']
                if 'stack' in processed_info:
                    processed_info = {'x': 1}
                return processed_info

        nb_actions = self.env.action_space.n

        self.dqn = DQNAgent(model=self.model, nb_actions=nb_actions, memory=self.memory, nb_steps_warmup=nb_steps_warmup,
                            target_model_update=1e-2, policy=policy,
                            processor=CustomPlayProcessor(),
                            batch_size=batch_size, train_interval=train_interval, enable_double_dqn=enable_double_dqn)
        self.dqn.compile(Adam(lr=1e-3), metrics=['mae'])  # pylint: disable=no-member

        self.dqn.test(self.env, nb_episodes=nb_episodes, visualize=render)

    def action(self, action_space, observation, info):  # pylint: disable=no-self-use
        """Mandatory method that calculates the move based on the observation array and the action space."""
        _ = observation  # not using the observation for random decision
        _ = info

        this_player_action_space = {Action.FOLD, Action.CHECK, Action.CALL, Action.RAISE_POT, Action.RAISE_HALF_POT,
                                    Action.RAISE_2POT}
        _ = this_player_action_space.intersection(set(action_space))

        action = None
        return action


class TrumpPolicy(BoltzmannQPolicy):
    """Custom policy when making decision based on neural network."""

    def select_action(self, q_values):
        """Return the selected action

        # Arguments
            q_values (np.ndarray): List of the estimations of Q for each action

        # Returns
            Selection action
        """
        assert q_values.ndim == 1
        q_values = q_values.astype('float64')
        nb_actions = q_values.shape[0]

        exp_values = np.exp(np.clip(q_values / self.tau, self.clip[0], self.clip[1]))
        probs = exp_values / np.sum(exp_values)
        action = np.random.choice(range(nb_actions), p=probs)

        log.debug(f"Chosen action by keras-rl {Action(action)}")
        log.debug(f"Probabilities: { {Action(i):probs[i] for i in range(len(probs))} }")
        return action


class CustomTrainProcessor(Processor):
    """The agent and the environment"""

    def __init__(self):
        """initizlie properties"""
        self.legal_moves_limit = None

    def process_state_batch(self, batch):
        """Remove second dimension to make it possible to pass it into cnn"""
        return np.squeeze(batch, axis=1)

    def process_info(self, info):
        if 'legal_moves' in info.keys():
            self.legal_moves_limit = info['legal_moves']
        else:
            self.legal_moves_limit = None
        return {'x': 1}  # on arrays allowed it seems
