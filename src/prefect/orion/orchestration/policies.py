from abc import ABC, abstractmethod


class BaseOrchestrationPolicy(ABC):
    @staticmethod
    @abstractmethod
    def priority():
        return []

    @classmethod
    def compile_transition_rules(cls, from_state=None, to_state=None):
        transition_rules = []
        for rule in cls.priority():
            if from_state in rule.FROM_STATES and to_state in rule.TO_STATES:
                transition_rules.append(rule)
        return transition_rules
