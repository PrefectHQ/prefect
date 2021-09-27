from abc import ABC, abstractmethod


class BaseOrchestrationPolicy(ABC):
    """
    An abstract base class used to organize orchestration rules in priority order.

    Different collections of orchestration rules might be used to govern various kinds
    of transitions. For example, flow-run states and task-run states might require
    different orchestration logic.
    """

    @staticmethod
    @abstractmethod
    def priority():
        """
        A list of orchestration rules in priority order.
        """

        return []

    @classmethod
    def compile_transition_rules(cls, from_state=None, to_state=None):
        """
        Returns rules in policy that are valid for the specified state transition.
        """

        transition_rules = []
        for rule in cls.priority():
            if from_state in rule.FROM_STATES and to_state in rule.TO_STATES:
                transition_rules.append(rule)
        return transition_rules
