from __future__ import annotations

from abc import ABC, abstractmethod
import random
from contextlib import suppress
from copy import deepcopy
from decimal import Decimal
from typing import Iterable, Counter, Callable, Optional, Type

from .exceptions import STVException, IncompleteResult
from .utils import Proposal, PreferenceBallot, ElectionResult, minmax, Votes, SelectionMethod

Quota = Callable[['STVPoll'], int]


class Tiebreaker(ABC):
    """ Tiebreaker classes are strategies to resolve ties between proposals """
    @property
    @abstractmethod
    def selection_method(self) -> SelectionMethod:
        ...

    def __init__(self, poll: STVPoll) -> None:
        self.poll = poll

    @abstractmethod
    def __call__(self, ties: list[Proposal], most_votes: bool = True) -> list[Proposal]:
        """
        Resolve ties, to whatever accuracy possible.
        Return any amount, from one to all supplied proposals.
        """


class STVPoll(ABC):
    multiple_winners = True
    _quota: int = None

    def __init__(self, *,
                 seats: int,
                 proposals: Iterable[Proposal],
                 quota: Quota = None,
                 tiebreakers: Iterable[Type[Tiebreaker]] = None,
                 pedantic_order: bool = False,       # Uses tiebreaks to decide order is elect_multiple
                 ) -> None:
        self.proposals = list(proposals)
        if len(self.proposals) < seats:
            raise STVException('Not enough candidates to fill seats')

        random.shuffle(self.proposals)

        self._quota_function = quota
        self.seats = seats
        self.pedantic_order = pedantic_order

        self.votes: Votes = {p: Decimal(0) for p in self.proposals}
        self.excluded: list[Proposal] = []
        self.ballots: list[PreferenceBallot] = []
        self.votes_transferred: set[Proposal] = set()
        self.result = ElectionResult(self)
        self.tiebreakers = [] if tiebreakers is None else [t(self) for t in tiebreakers]

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

    def resolve_tie(self, ties: list[Proposal], most_votes: bool = True) -> tuple[Proposal, SelectionMethod]:
        """
        Loops through available tiebreakers until there is exactly one proposal,
        or results in incomplete result for poll.
        """
        for tiebreaker in self.tiebreakers:
            ties = tiebreaker(ties, most_votes)
            if len(ties) == 1:
                return ties[0], tiebreaker.selection_method
        raise IncompleteResult('Could not resolve tie')

    def transfer_votes(self, proposal: Proposal, fraction: Decimal = Decimal(1)) -> None:
        transfers = Counter[tuple[Proposal, Proposal]]()
        for ballot in self.ballots:
            if proposal == ballot.current_preference:
                ballot.decrease_value(fraction)
                if target_proposal := ballot.get_transfer_preference(self.standing_proposals):
                    self.votes[target_proposal] += ballot.value
                    transfers[(proposal, target_proposal)] += ballot.value
                else:
                    self.result.exhausted += ballot.value
        self.votes.pop(proposal)                     # Remove from future vote counts
        self.votes_transferred.add(proposal)         # Mark as transferred

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

    def get_ties(self,
                 proposal: Proposal,
                 sample: list[Proposal] = None,
                 votes: Votes = None
                 ) -> Optional[list[Proposal]]:
        """ Get all proposals that are tied in amount of votes. """
        if votes is None:
            # Default to current votes
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

    def get_transferable_proposals(self) -> list[Proposal]:
        """ Winning proposals that has not yet gotten it's votes transferred """
        standing = self.standing_proposals
        return [p for p in self.proposals if p not in standing and p not in self.votes_transferred]

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
        """ Sets initial votes and calculates a result """
        self.initial_votes()
        with suppress(IncompleteResult):
            self.perform_calculation()
        self.result.finish()
        return self.result

    @abstractmethod
    def perform_calculation(self) -> None:
        """ Implement is subclasses to calculate a result. """


class STVRoundsPoll(STVPoll):
    def perform_calculation(self) -> None:
        while self.seats_to_fill:
            self.calculate_round()

    @abstractmethod
    def calculate_round(self) -> None:
        """ Calculate an election round in implementation class """
