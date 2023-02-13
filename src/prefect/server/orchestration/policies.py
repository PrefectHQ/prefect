"""
Policies are collections of orchestration rules and transforms.

Prefect implements (most) orchestration with logic that governs a Prefect flow or task
changing state. Policies organize of orchestration logic both to provide an ordering
mechanism as well as provide observability into the orchestration process.

While Prefect's [orchestration rules][prefect.server.orchestration.rules.BaseOrchestrationRule]
can gracefully run independently of one another, ordering can still have an impact on
the observed behavior of the system. For example, it makes no sense to secure a
concurrency slot for a run if a cached state exists. Furthermore, policies, provide a
mechanism to configure and observe exactly what logic will fire against a transition.
"""

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
