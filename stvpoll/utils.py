from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from decimal import Decimal
from enum import Enum
from time import time
from typing import Iterable, Union, TYPE_CHECKING, Callable, TypedDict, Counter

if TYPE_CHECKING:
    from .abcs import STVPoll


Proposal = Union[str, int]
Votes = dict[Proposal, Decimal]


def minmax(items: Iterable, key: Callable[[Proposal], Decimal] = None, high: bool = True):
    if high:
        return max(items, key=key)
    return min(items, key=key)


class PreferenceBallot:
    def __init__(self, preferences: list[Proposal], count: int) -> None:
        self.preferences = preferences
        self.count = count
        self.multiplier = Decimal(1)
        self.index = 0

    def __len__(self):
        return len(self.preferences)

    @property
    def value(self):
        return self.multiplier * self.count

    def decrease_value(self, multiplier: Decimal):
        self.multiplier *= multiplier

    @property
    def current_preference(self):
        with suppress(IndexError):
            return self.preferences[self.index]

    @property
    def exhausted(self) -> bool:
        return self.index >= len(self)

    def get_transfer_preference(self, standing_proposals: list[Proposal]):
        while not self.exhausted:
            self.index += 1
            if self.current_preference in standing_proposals:
                return self.current_preference


class ProposalStatus(str, Enum):
    Elected = 'elected'
    Excluded = 'excluded'
    Hopeful = 'hopeful'


class SelectionMethod(str, Enum):
    Direct = 'direct'
    History = 'tiebreak_history'
    Random = 'tiebreak_random'
    NoCompetition = 'no_competition_left'
    CPO = 'cpo'


class ElectionRound:
    status: ProposalStatus = None
    selection_method: SelectionMethod = None

    def __init__(self, index: int, votes: Votes) -> None:
        self.index = index
        self.selected: list[Proposal] = []
        self.votes = deepcopy(votes)

    def select(self,
               proposals: Union[Proposal, list[Proposal]],
               method: SelectionMethod,
               status: ProposalStatus,
               ) -> None:
        if isinstance(proposals, list):
            self.selected += proposals
        else:
            self.selected.append(proposals)
        self.selection_method = method
        self.status = status

    def __repr__(self) -> str:  # pragma: no coverage
        proposals = ', '.join(p for p in self.selected)
        method = f' ({self.selection_method})' if self.selection_method else ''
        return f'<ElectionRound {self.index}: {self.status} {proposals}{method}>'

    def as_dict(self) -> dict:
        return {
            'status': self.status.value,
            'selected': tuple(self.selected),
            'method': self.selection_method.value,
            'vote_count': tuple(self.votes.items()),
        }


class TransferLogItem(TypedDict):
    transfers: Union[Counter[tuple[Proposal, Proposal]], None]
    current_votes: Votes
    exhausted_votes: int


class ElectionResult:
    exhausted = Decimal(0)
    runtime = .0
    randomized = False
    empty_ballot_count = 0

    def __init__(self, poll: STVPoll):
        self.poll = poll
        self.rounds: list[ElectionRound] = []
        self.elected: list[Proposal] = []
        self.start_time = time()
        self.transfer_log: list[TransferLogItem] = []
        self.extra_data = {}        # Can be populated by for example tiebreakers

    def __repr__(self) -> str:  # pragma: no coverage
        return f'<ElectionResult in {len(self.rounds)} round(s): {", ".join(map(str, self.elected))}>'

    def new_round(self, votes: Votes):
        self.rounds.append(
            ElectionRound(len(self.rounds) + 1, votes)
        )

    def finish(self):
        self.runtime = time() - self.start_time

    @property
    def current_round(self) -> ElectionRound:
        return self.rounds[-1]

    def elect(self, proposals: Union[Proposal, list[Proposal]], method: SelectionMethod) -> None:
        if isinstance(proposals, list):
            self.elected += proposals
        else:
            self.elected.append(proposals)
        self.current_round.select(proposals, method, ProposalStatus.Elected)

    def exclude(self, proposals: Union[Proposal, list[Proposal]], method: SelectionMethod) -> None:
        self.current_round.select(proposals, method, ProposalStatus.Excluded)

    @property
    def is_complete(self) -> bool:
        return len(self.elected) == self.poll.seats

    def elected_as_tuple(self) -> tuple[Proposal]:
        return tuple(self.elected)

    def elected_as_set(self) -> set[Proposal]:
        return set(self.elected)

    def as_dict(self) -> dict:
        return {
            'winners': self.elected_as_tuple(),
            'proposals': tuple(self.poll.proposals),
            'complete': self.is_complete,
            'rounds': tuple(r.as_dict() for r in self.rounds),
            'quota': self.poll.quota,
            'runtime': self.runtime,
            'empty_ballot_count': self.empty_ballot_count,
            **self.extra_data,
        }
