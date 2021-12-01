from decimal import Decimal
from math import floor, ceil

from stvpoll.abcs import STVRoundsPoll
from stvpoll.exceptions import IncompleteResult
from stvpoll.tiebreakers import RandomListTiebreaker
from stvpoll.utils import SelectionMethod


def irv_quota(poll: STVRoundsPoll) -> int:
    """ More than 50 % of votes """
    return int(floor(Decimal(poll.ballot_count + poll.result.empty_ballot_count) / 2)) + 1


class IRV(STVRoundsPoll):
    multiple_winners = False

    def __init__(self, **kwargs):
        kwargs.setdefault('quota', irv_quota)
        if kwargs.pop('random_in_tiebreaks', True):
            kwargs.setdefault('tiebreakers', [RandomListTiebreaker])
        kwargs['seats'] = 1
        super().__init__(**kwargs)

    def calculate_round(self) -> None:
        # First, check if there is a winner
        for proposal in self.standing_proposals:
            if self.get_votes(proposal) >= self.quota:
                return self.elect(proposal, SelectionMethod.Direct)

        if len(self.standing_proposals) == 1:
            raise IncompleteResult('No candidate can get majority.')

        loser, method = self.get_proposal(most_votes=False)
        self.exclude(loser, method)
        self.transfer_votes(loser)
