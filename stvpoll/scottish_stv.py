from decimal import Decimal

from stvpoll.abcs import STVRoundsPoll
from stvpoll.quotas import droop_quota
from stvpoll.tiebreakers import TransferHistoryTiebreaker, RandomListTiebreaker
from stvpoll.utils import SelectionMethod, Proposal


class ScottishSTV(STVRoundsPoll):
    def __init__(self, **kwargs) -> None:
        tiebreakers = [TransferHistoryTiebreaker]
        if kwargs.pop('random_in_tiebreaks', True):
            tiebreakers.append(RandomListTiebreaker)
        kwargs.setdefault('quota', droop_quota)
        kwargs.setdefault('tiebreakers', tiebreakers)
        super().__init__(**kwargs)

    @staticmethod
    def round(value: Decimal) -> Decimal:
        return round(value, 5)

    def get_transfer_fraction(self, proposal: Proposal) -> Decimal:
        votes = self.get_votes(proposal)
        return ScottishSTV.round((votes - self.quota) / votes)

    def calculate_round(self) -> None:
        # First, declare winners if any are over quota
        above_quota = self.standing_above_quota
        if above_quota:
            return self.elect_multiple(
                above_quota,
                SelectionMethod.Direct,
            )

        # Transfer only one proposals votes at a time, in order of most votes. Resolve ties.
        # Any new proposals above quota should be elected before transferring further votes.
        if transferable := self.get_transferable_proposals():
            proposal, _ = self.get_proposal(sample=transferable)
            return self.transfer_votes(proposal, self.get_transfer_fraction(proposal))

        # In case of vote exhaustion, this is theoretically possible.
        if self.seats_to_fill == len(self.standing_proposals):
            return self.elect_multiple(
                self.standing_proposals,
                SelectionMethod.NoCompetition,
            )

        # Else exclude a candidate
        proposal, method = self.get_proposal(most_votes=False)
        self.exclude(proposal, method)
        self.transfer_votes(proposal)
