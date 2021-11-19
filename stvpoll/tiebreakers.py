from functools import cached_property
from random import shuffle, sample

from stvpoll.abcs import Tiebreaker, STVPoll
from stvpoll.utils import Proposal, minmax, SelectionMethod


class RandomListTiebreaker(Tiebreaker):
    """
    Resolve ties by using a pre-shuffled list
    """
    selection_method = SelectionMethod.Random

    def __init__(self, poll: STVPoll) -> None:
        super().__init__(poll)
        self.result_randomized(False)

    @cached_property
    def random_list(self) -> list[Proposal]:
        return sample(self.poll.proposals, len(self.poll.proposals))

    def result_randomized(self, value: bool = True):
        extra_data = self.poll.result.extra_data
        if extra_data.get('randomized') == value:
            return
        extra_data['randomized'] = value
        if value:
            extra_data['randomized_proposal_list'] = self.random_list

    def __call__(self, ties: list[Proposal], most_votes: bool = True) -> list[Proposal]:
        self.result_randomized()
        order = self.random_list if most_votes else self.random_list[::-1]
        return [next(p for p in order if p in ties)]


class TransferHistoryTiebreaker(Tiebreaker):
    """
    Resolve ties by looking at vote transfer history,
    prioritizing proposals that was in the lead at an earlier point
    """
    selection_method = SelectionMethod.History

    def __call__(self, ties: list[Proposal], most_votes: bool = True) -> list[Proposal]:
        for stage in self.poll.result.transfer_log[::-1]:
            stage_votes = stage['current_votes']
            primary_candidate = minmax(ties, key=lambda p: stage_votes[p], high=most_votes)
            stage_ties = self.poll.get_ties(primary_candidate, ties, stage_votes)
            if not stage_ties:
                return [primary_candidate]
            ties = stage_ties
        return ties
