from __future__ import annotations

from abc import ABC, abstractmethod
import random
from contextlib import suppress
from copy import deepcopy
from decimal import Decimal
from typing import Iterable, Counter, Callable

from .exceptions import STVException, IncompleteResult
from .utils import Proposal, PreferenceBallot, ElectionResult, minmax, Votes, SelectionMethod, ProposalStatus

Quota = Callable[['STVPoll'], int]


class STVPoll(ABC):
    _quota: int = None
    ballots: list[PreferenceBallot]

    def __init__(self,
                 seats: int,
                 proposals: Iterable[Proposal],
                 quota: Quota = None,
                 random_in_tiebreaks: bool = True,
                 pedantic_order: bool = False,
                 ) -> None:
        self.proposals = list(proposals)
        random.shuffle(self.proposals)
        self.votes: Votes = {p: 0 for p in self.proposals}
        self.excluded = list[Proposal]()
        self.ballots = []
        self._quota_function = quota
        self.seats = seats
        self.random_in_tiebreaks = random_in_tiebreaks
        self.pedantic_order = pedantic_order
        self.result = ElectionResult(self)
        if len(self.proposals) < self.seats:
            raise STVException('Not enough candidates to fill seats')

    @property
    def quota(self) -> int:
        if self._quota is None:
            self._quota = self._quota_function(self)
        return self._quota

    @property
    def ballot_count(self) -> int:
        return sum(b.count for b in self.ballots)

    def add_ballot(self, ranking: list[Proposal], count: int = 1) -> None:
        # Empty votes will not affect quota, but will be accounted for in result.
        if ranking:
            self.ballots.append(PreferenceBallot(ranking, count))
        else:
            self.result.empty_ballot_count += count

    def get_votes(self, proposal: Proposal) -> Decimal:
        return self.votes[proposal]

    def get_proposal(self, most_votes: bool = True, sample: list[Proposal] = None) -> tuple[Proposal, SelectionMethod]:
        if sample is None:
            sample = self.standing_proposals
        proposal = minmax(sample, key=self.get_votes, high=most_votes)
        ties = self.get_ties(proposal)
        if ties:
            return self.resolve_tie(ties, most_votes)
        return proposal, SelectionMethod.Direct

    def choice(self, proposals: list[Proposal]) -> Proposal:
        if self.random_in_tiebreaks:
            self.result.randomized = True
            return random.choice(proposals)
        raise IncompleteResult('Unresolved tiebreak (random disallowed)')

    def resolve_tie(self, proposals: list[Proposal], most_votes: bool = True) -> tuple[Proposal, SelectionMethod]:
        for stage in self.result.transfer_log[::-1]:
            stage_votes = stage['current_votes']
            primary_candidate = minmax(proposals, key=lambda p: stage_votes[p], high=most_votes)
            ties = self.get_ties(primary_candidate, proposals, stage_votes)
            if ties:
                proposals = ties
            else:
                return primary_candidate, SelectionMethod.History
        return self.choice(proposals), SelectionMethod.Random

    def transfer_votes(self, prop_quotas: dict[Proposal, Decimal]) -> None:
        transfers = Counter[tuple[Proposal, Proposal]]()
        for ballot in self.ballots:
            proposal = ballot.current_preference
            if proposal in prop_quotas:
                ballot.decrease_value(prop_quotas[proposal])
                if target_proposal := ballot.get_transfer_preference(self.standing_proposals):
                    self.votes[target_proposal] += ballot.value
                    transfers[(proposal, target_proposal)] += ballot.value
                else:
                    self.result.exhausted += ballot.value
        for proposal in prop_quotas:
            self.votes.pop(proposal)

        self.result.transfer_log.append({
            'transfers': transfers,
            'current_votes': self.current_votes,
            'exhausted_votes': self.result.exhausted,
        })

    def initial_votes(self) -> None:
        for ballot in self.ballots:
            assert ballot.current_preference, 'Initial votes called with an empty vote'
            self.votes[ballot.current_preference] += ballot.value

        self.result.transfer_log.append({
            'transfers': None,
            'current_votes': self.current_votes,
            'exhausted_votes': self.result.exhausted,
        })

    def get_ties(self, proposal: Proposal, sample: list[Proposal] = None, votes: Votes = None) -> list[Proposal]:
        # Use current votes is none supplied
        if votes is None:
            votes = self.votes
        proposal_votes = votes[proposal]
        if sample is None:
            sample = self.standing_proposals
        ties = [p for p in sample if votes[p] == proposal_votes]
        if len(ties) > 1:
            return ties

    @property
    def standing_proposals(self) -> list[Proposal]:
        return [p for p in self.proposals if p not in self.excluded and p not in self.result.elected]

    @property
    def standing_above_quota(self) -> list[Proposal]:
        return [p for p in self.standing_proposals if self.get_votes(p) >= self.quota]

    @property
    def current_votes(self) -> dict[Proposal, Decimal]:
        return deepcopy(self.votes)

    @property
    def seats_to_fill(self) -> int:
        return self.seats - len(self.result.elected)

    @property
    def is_complete(self) -> bool:
        return self.result.is_complete

    def elect(self, proposal: Proposal, method: SelectionMethod) -> None:
        self.result.new_round(self.current_votes)
        self.result.elect(
            proposal, method
        )

    def elect_multiple(self, proposals: list[Proposal], method: SelectionMethod) -> None:
        if proposals:
            self.result.new_round(self.current_votes)
            if self.pedantic_order:
                # Select candidates in order, resolving ties.
                while proposals:
                    proposal, method = self.get_proposal(
                        sample=proposals
                    )
                    self.result.elect(
                        proposal, method
                    )
            else:
                # Select candidates in order, not bothering with ties.
                self.result.elect(
                    sorted(proposals, key=self.get_votes, reverse=True), method
                )

    def exclude(self, proposal: Proposal, method: SelectionMethod) -> None:
        self.excluded.append(proposal)
        self.result.new_round(self.current_votes)
        self.result.exclude(proposal, method)

    def calculate(self) -> ElectionResult:
        # if not self.ballots:  # pragma: no coverage
        #     raise STVException('No ballots registered.')
        self.initial_votes()
        with suppress(IncompleteResult):
            self.do_rounds()
        self.result.finish()
        return self.result

    def do_rounds(self) -> None:
        while self.seats_to_fill:
            self.calculate_round()

    @abstractmethod
    def calculate_round(self) -> None:
        """ Calculate an election round in implementation class """
