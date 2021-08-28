from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import product


class BaseOrchestrationPolicy(ABC):
    @abstractmethod
    def REGISTERED_RULES():
        return []

    @abstractmethod
    def TRANSITION_TABLE():
        return defaultdict(list)

    @staticmethod
    @abstractmethod
    def priority():
        return []

    @classmethod
    def register(cls, orchestration_rule):
        cls.REGISTERED_RULES.append(orchestration_rule)
        for transition in product(
            orchestration_rule.FROM_STATES, orchestration_rule.TO_STATES
        ):
            cls.TRANSITION_TABLE[tuple(transition)].append(orchestration_rule)
        return orchestration_rule

    @classmethod
    def lookup_transition_rules(cls, from_state=None, to_state=None):
        transition_rules = cls.TRANSITION_TABLE[(from_state, to_state)]
        return list(
            sorted(transition_rules, key=lambda rule: cls.priority().index(rule))
        )
