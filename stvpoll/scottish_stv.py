from decimal import Decimal

from stvpoll.abcs import STVPoll
from stvpoll.quotas import droop_quota
from stvpoll.utils import SelectionMethod, Proposal


class ScottishSTV(STVPoll):

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault('quota', droop_quota)
        super().__init__(*args, **kwargs)

    @staticmethod
    def round(value: Decimal) -> Decimal:
        return round(value, 5)

    def get_transfer_quota(self, proposal: Proposal) -> Decimal:
        votes = self.get_votes(proposal)
        return (votes - self.quota) / votes

    def calculate_round(self) -> None:
        # First, declare winners if any are over quota
        above_quota = self.standing_above_quota
        if above_quota:
            self.elect_multiple(
                above_quota,
                SelectionMethod.Direct,
            )
            # If there there are winner votes to transfer, then do that.
            return self.transfer_votes(
                {p: self.get_transfer_quota(p) for p in above_quota}
            )

        # In case of vote exhaustion, this is theoretically possible.
        if self.seats_to_fill == len(self.standing_proposals):
            return self.elect_multiple(
                self.standing_proposals,
                SelectionMethod.NoCompetition,
            )

        # Else exclude a candidate
        proposal, method = self.get_proposal(most_votes=False)
        self.exclude(proposal, method)
        self.transfer_votes({proposal: Decimal(1)})
