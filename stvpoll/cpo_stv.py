from __future__ import annotations

from decimal import Decimal
from itertools import combinations
from math import factorial
from random import choice

from typing import Iterable, DefaultDict

from stvpoll.abcs import STVPoll
from stvpoll.exceptions import IncompleteResult
from stvpoll.quotas import hagenbach_bischof_quota
from stvpoll.utils import Proposal, SelectionMethod


class CPOComparisonPoll(STVPoll):
    def __init__(self, *,
                 winners: set,
                 compared: set,
                 **kwargs
                 ) -> None:
        kwargs.setdefault('quota', hagenbach_bischof_quota)
        super().__init__(**kwargs)
        self.compared = compared
        self.winners = winners
        self.below_quota = False

    def get_transfer_fraction(self, proposal: Proposal) -> Decimal:
        votes = self.get_votes(proposal)
        return (votes - self.quota) / votes

    def perform_calculation(self) -> None:
        """ CPO rounds work differently than other STV methods """
        for exclude in set(self.standing_proposals).difference(self.winners):
            self.exclude(exclude, SelectionMethod.Direct)
            self.transfer_votes(exclude)

        elect = list(set(self.standing_proposals).difference(self.compared))
        self.elect_multiple(elect, SelectionMethod.Direct)
        for prop in elect:
            self.transfer_votes(prop, self.get_transfer_fraction(prop))
            self.votes[prop] = Decimal(self.quota)

    @property
    def not_excluded(self) -> list[Proposal]:
        return [p for p in self.proposals if p not in self.excluded]

    def total_except(self, proposals: list[Proposal]) -> Decimal:
        return sum(self.get_votes(p) for p in self.not_excluded if p not in proposals)


class CPOComparisonResult:
    def __init__(self, poll: CPOComparisonPoll, compared: tuple[list[Proposal], list[Proposal]]) -> None:
        self.poll = poll
        self.compared = compared
        self.all = set(compared[0] + compared[1])
        self.totals: list[tuple[list[Proposal], Decimal]] = sorted([
            (compared[0], self.total(compared[0])),
            (compared[1], self.total(compared[1])),
        ], key=lambda c: c[1])
        # May be unclear here, but winner or looser does not matter if tied
        self.loser = self.totals[0][0]
        self.winner = self.totals[1][0]
        self.difference = self.totals[1][1] - self.totals[0][1]
        self.tied = self.difference == 0

    def others(self, combination: list[Proposal]) -> Iterable[Proposal]:
        return self.all.difference(combination)

    def total(self, combination: list[Proposal]) -> Decimal:
        return self.poll.total_except(list(self.others(combination)))


class CPO_STV(STVPoll):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault('quota', hagenbach_bischof_quota)
        kwargs['pedantic_order'] = False
        self.random_in_tiebreaks = kwargs.pop('random_in_tiebreaks', True)
        super().__init__(**kwargs)
        if self.random_in_tiebreaks:
            self.result.extra_data['randomized'] = False

    @staticmethod
    def possible_combinations(proposals: int, winners: int) -> int:
        return factorial(proposals) // factorial(winners) // factorial(proposals - winners)

    def get_best_approval(self) -> list[Proposal]:
        # If no more seats to fill, there will be no duels. Return empty list.
        if self.seats_to_fill == 0:
            return []

        duels = []
        possible_outcomes = list(combinations(self.standing_proposals, self.seats_to_fill))
        for combination in combinations(possible_outcomes, 2):
            compared = set([c for sublist in combination for c in sublist])
            winners = set(compared)
            winners.update(self.result.elected)
            comparison_poll = CPOComparisonPoll(
                seats=self.seats,
                proposals=self.proposals,
                winners=winners,
                compared=compared)

            for ballot in self.ballots:
                comparison_poll.add_ballot(ballot.preferences, ballot.count)

            comparison_poll.calculate()
            duels.append(CPOComparisonResult(
                comparison_poll,
                combination))

        # Return either a clear winner (no ties), or resolved using MiniMax
        return self.get_duels_winner(duels) or self.resolve_tie_minimax(duels)
        # ... Ranked Pairs (so slow)
        # return self.get_duels_winner(duels) or self.resolve_tie_ranked_pairs(duels)

    def get_duels_winner(self, duels: list[CPOComparisonResult]) -> list[Proposal]:
        wins = set()
        losses = set()
        for duel in duels:
            losses.add(duel.loser)
            if duel.tied:
                losses.add(duel.winner)
            else:
                wins.add(duel.winner)

        undefeated = wins - losses
        if len(undefeated) == 1:
            # If there is ONE clear winner (won all duels), return that combination.
            return undefeated.pop()
        # No clear winner
        return []

    def choice(self, ties: list[tuple[Proposal]]):
        if not self.random_in_tiebreaks:
            raise IncompleteResult('Could not resolve ties')
        self.result.extra_data['randomized'] = True
        return choice(ties)

    def resolve_tie_minimax(self, duels: list[CPOComparisonResult]) -> tuple[Proposal]:
        from tarjan import tarjan
        graph = DefaultDict[list[Proposal], list[list[Proposal]]](list)
        for d in duels:
            graph[d.loser].append(d.winner)
            if d.tied:                            # Ties go both ways
                graph[d.winner].append(d.loser)
        smith_set: list[tuple[Proposal]] = tarjan(graph)[0]

        biggest_defeats: dict[tuple[Proposal], Decimal] = {}
        for proposals in smith_set:
            # Get CPOComparisonResults where proposals loses or ties
            ds = filter(lambda d: d.loser == proposals or (d.tied and d.winner == proposals), duels)
            biggest_defeats[proposals] = max(d.difference for d in ds)
        minimal_defeat = min(biggest_defeats.values())
        ties = [props for props, diff in biggest_defeats.items() if diff == minimal_defeat]
        if len(ties) > 1:
            return self.choice(ties)
        return ties[0]  # pragma: no cover

    # def resolve_tie_ranked_pairs(self, duels):
    #     # type: (List[CPOComparisonResult]) -> List[Candidate]
    #     # https://medium.com/freds-blog/explaining-the-condorcet-system-9b4f47aa4e60
    #     class TracebackFound(STVException):
    #         pass
    #
    #     def traceback(duel, _trace=None):
    #         # type: (CPOComparisonResult, CPOComparisonResult) -> None
    #         for trace in filter(lambda d: d.winner == (_trace and _trace.loser or duel.loser), noncircular_duels):
    #             if duel.winner == trace.loser:
    #                 raise TracebackFound()
    #             traceback(duel, trace)
    #
    #     difference_groups = {}
    #     # filter: Can't declare winners if duel was tied.
    #     for d in filter(lambda d: not d.tied, duels):
    #         try:
    #             difference_groups[d.difference].append(d)
    #         except KeyError:
    #             difference_groups[d.difference] = [d]
    #
    #     noncircular_duels = []
    #
    #     # Check if there are equal difference duels
    #     # Need to make sure these do not cause tiebreaks depending on order
    #     for difference in sorted(difference_groups.keys(), reverse=True):
    #         saved_list = noncircular_duels[:]
    #         group = difference_groups[difference]
    #         try:
    #             for duel in group:
    #                 traceback(duel)
    #                 noncircular_duels.append(duel)
    #         except TracebackFound:
    #             if len(group) > 1:
    #                 noncircular_duels = saved_list
    #                 while group:
    #                     duel = self.choice(group)
    #                     try:
    #                         traceback(duel)
    #                         noncircular_duels.append(duel)
    #                     except TracebackFound:
    #                         pass
    #                     group.remove(duel)
    #
    #     return self.get_duels_winner(noncircular_duels)

    def perform_calculation(self) -> None:
        if len(self.proposals) == self.seats:
            self.elect_multiple(
                self.proposals,
                SelectionMethod.Direct)
            return

        self.elect_multiple(
            [p for p in self.proposals if self.get_votes(p) > self.quota],
            SelectionMethod.Direct)

        self.elect_multiple(
            self.get_best_approval(),
            SelectionMethod.CPO)
