from prefect.server.orchestration.policies import BaseOrchestrationPolicy
from prefect.server.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseOrchestrationRule,
)
from prefect.server.schemas import states


class TestPoliciesRespectOrdering:
    def test_policies_return_rules_in_priority_order(self):
        class FirstRuleOfFightClub(BaseOrchestrationRule):
            TO_STATES = ALL_ORCHESTRATION_STATES
            FROM_STATES = ALL_ORCHESTRATION_STATES

            def before_transition(self, initial_state, proposed_state, context):
                "we don't talk about fight club"

        class SecondRuleOfFightClub(BaseOrchestrationRule):
            TO_STATES = ALL_ORCHESTRATION_STATES
            FROM_STATES = ALL_ORCHESTRATION_STATES

            def before_transition(self, initial_state, proposed_state, context):
                "we don't talk about fight club"

        class FightClub(BaseOrchestrationPolicy):
            @staticmethod
            def priority():
                return [
                    FirstRuleOfFightClub,
                    SecondRuleOfFightClub,
                ]

        class CopyCatClub(BaseOrchestrationPolicy):
            @staticmethod
            def priority():
                return [
                    FirstRuleOfFightClub,
                    SecondRuleOfFightClub,
                ]

        class DefinitelyADifferentClub(BaseOrchestrationPolicy):
            @staticmethod
            def priority():
                return [
                    SecondRuleOfFightClub,
                    FirstRuleOfFightClub,
                ]

        transition = (states.StateType.RUNNING, states.StateType.COMPLETED)
        fight_club_rules = FightClub.compile_transition_rules(*transition)
        copycat_rules = CopyCatClub.compile_transition_rules(*transition)
        definitely_different_rules = DefinitelyADifferentClub.compile_transition_rules(
            *transition
        )
        assert fight_club_rules == copycat_rules
        assert fight_club_rules != definitely_different_rules

    def test_policies_only_return_relevant_rules(self):
        class UnenforcableRule(BaseOrchestrationRule):
            TO_STATES = []
            FROM_STATES = []

        class UselessRule(BaseOrchestrationRule):
            TO_STATES = []
            FROM_STATES = []

        class ValidRule(BaseOrchestrationRule):
            TO_STATES = ALL_ORCHESTRATION_STATES
            FROM_STATES = ALL_ORCHESTRATION_STATES

        class Bureaucracy(BaseOrchestrationPolicy):
            @staticmethod
            def priority():
                return [
                    UselessRule,
                    UnenforcableRule,
                    ValidRule,
                ]

        transition = (states.StateType.PENDING, states.StateType.RUNNING)
        assert Bureaucracy.compile_transition_rules(*transition) == [ValidRule]
