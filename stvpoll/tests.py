# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import os
import json
from codecs import open

from stvpoll import STVPollBase
from stvpoll.scottish_stv import ScottishSTV
from stvpoll.cpo_stv import CPO_STV
from typing import Type


def _opa_example_fixture(factory):
    """
    28 voters ranked Alice first, Bob second, and Chris third
    26 voters ranked Bob first, Alice second, and Chris third
    3 voters ranked Chris first
    2 voters ranked Don first
    1 voter ranked Eric first
    """
    obj = factory(seats=3, candidates=['Alice', 'Bob', 'Chris', 'Don', 'Eric'])
    obj.add_ballot(['Alice', 'Bob', 'Chris'], 28)
    obj.add_ballot(['Bob', 'Alice', 'Chris'], 26)
    obj.add_ballot(['Chris'], 3)
    obj.add_ballot(['Don'], 2)
    obj.add_ballot(['Eric'], 1)
    return obj

def _wikipedia_example_fixture(factory):
    """
    Example from https://en.wikipedia.org/wiki/Single_transferable_vote
    """
    example_ballots = (
        (('orange',), 4),
        (('pear', 'orange',), 2),
        (('chocolate', 'strawberry',), 8),
        (('chocolate', 'bonbon',), 4),
        (('strawberry',), 1),
        (('bonbon',), 1),
    )
    obj = factory(seats=3, candidates=('orange', 'chocolate', 'pear', 'strawberry', 'bonbon'))
    for b in example_ballots:
        obj.add_ballot(*b)
    return obj


def _wikipedia_cpo_example_fixture(factory):
    """
    Example from https://en.wikipedia.org/wiki/CPO-STV
    """
    example_candidates = ('Andrea', 'Carter', 'Brad', 'Delilah', 'Scott')
    example_ballots = (
        (('Andrea',), 25),
        (('Carter', 'Brad', 'Delilah'), 34),
        (('Brad', 'Delilah'), 7),
        (('Delilah', 'Brad'), 8),
        (('Delilah', 'Scott'), 5),
        (('Scott', 'Delilah'), 21),
    )
    obj = factory(seats=3, candidates=example_candidates)
    for b in example_ballots:
        obj.add_ballot(*b)
    return obj


def _CPO_extreme_tie_fixture(factory):
    # type: (Type[STVPollBase]) -> STVPollBase
    """
    Example from https://en.wikipedia.org/wiki/CPO-STV
    """
    example_candidates = ('Andrea', 'Batman', 'Robin', 'Gorm')
    example_ballots = (
        (('Andrea', 'Batman', 'Robin'), 1),
        (('Robin', 'Andrea', 'Batman'), 1),
        (('Batman', 'Robin', 'Andrea'), 1),
        (('Gorm',), 2),
    )
    obj = factory(seats=2, candidates=example_candidates)
    for b in example_ballots:
        obj.add_ballot(*b)
    return obj


def _scottish_tiebreak_history_fixture(factory):
    # type: (Type[STVPollBase]) -> STVPollBase
    """
    Example from https://en.wikipedia.org/wiki/CPO-STV
    """
    example_candidates = ('Andrea', 'Robin', 'Gorm')
    example_ballots = (
        (('Andrea', ), 3),
        (('Robin', ), 2),
        (('Gorm', 'Robin'), 1),
        ((), 3),
    )
    obj = factory(seats=1, candidates=example_candidates, quota=lambda x: 100)
    for b in example_ballots:
        obj.add_ballot(*b)
    return obj


def _incomplete_result_fixture(factory):
    # type: (Type[STVPollBase]) -> STVPollBase
    """
    Example from https://en.wikipedia.org/wiki/CPO-STV
    """
    example_candidates = ('Andrea', 'Batman', 'Robin', 'Gorm')
    example_ballots = (
        (('Batman',), 1),
        (('Gorm',), 2),
    )
    obj = factory(seats=3, candidates=example_candidates, random_in_tiebreaks=False)
    for b in example_ballots:
        obj.add_ballot(*b)
    return obj


def _big_fixture(factory, candidates, seats):
    with open('stvpoll/testdata/70 in 35.json') as infile:
        votedata = json.load(infile)
    obj = factory(candidates=votedata['candidates'][:candidates], seats=seats)
    for b in votedata['ballots']:
        obj.add_ballot(b, 1)
    return obj


def _tie_break_that_breaks(factory):
    example_candidates = \
        [u'A', u'B', u'C', u'D', u'E', u'F']
    example_ballots = (
        ([u'A', u'D',u'C'], 1),
        ([u'E', u'C', u'A', u'B'], 1),
    )
    obj = factory(seats=3, candidates=example_candidates, random_in_tiebreaks=True)
    for b in example_ballots:
        obj.add_ballot(*b)
    return obj


class STVPollBaseTests(unittest.TestCase):

    @property
    def _cut(self):
        from stvpoll.scottish_stv import ScottishSTV
        return ScottishSTV

    def test_ballot_count(self):
        obj = self._cut(seats=0, candidates=('a', 'b'))
        obj.add_ballot(['a', 'b'], 5)
        obj.add_ballot(['a'], 3)
        obj.add_ballot(['b'], 8)
        self.assertEqual(obj.ballot_count, 16)

    def test_add_ballot(self):
        obj = self._cut(seats=0, candidates=('a', 'b'))
        obj.add_ballot(['a', 'b'])
        obj.add_ballot(['a', 'b'])
        obj.add_ballot(['a', 'b'])
        obj.add_ballot(['a'])
        obj.add_ballot(['a'])
        obj.add_ballot(['b'])
        self.assertEqual(obj.ballot_count, 6)


class ScottishSTVTests(unittest.TestCase):
    opa_results = {'Alice', 'Bob', 'Chris'}
    wiki_results = {'chocolate', 'strawberry', 'orange'}
    wiki_cpo_results = {'Carter', 'Scott', 'Andrea'}

    @property
    def _cut(self):
        # type: () -> Type[ScottishSTV]
        return ScottishSTV

    def test_opa_example(self):
        obj = _opa_example_fixture(self._cut)
        result = obj.calculate()
        self.assertEqual(result.elected_as_set(), self.opa_results)
        self.assertEqual(result.as_dict()['randomized'], False)

    def test_wikipedia_example(self):
        obj = _wikipedia_example_fixture(self._cut)
        result = obj.calculate()
        self.assertEqual(result.elected_as_set(), self.wiki_results)
        self.assertEqual(result.as_dict()['randomized'], False)

    def test_wikipedia_cpo_example(self):
        obj = _wikipedia_cpo_example_fixture(self._cut)
        result = obj.calculate()
        self.assertEqual(result.elected_as_set(), self.wiki_cpo_results)
        self.assertEqual(result.as_dict()['randomized'], False)

    def test_tiebreak_randomized(self):
        obj = _CPO_extreme_tie_fixture(self._cut)
        result = obj.calculate()
        self.assertEqual(result.as_dict()['randomized'], True)
        self.assertEqual(result.as_dict()['complete'], True)
        self.assertEqual(result.as_dict()['empty_ballot_count'], 0)

    def test_scottish_tiebreak_history(self):
        obj = _scottish_tiebreak_history_fixture(self._cut)
        result = obj.calculate()
        try:
            self.assertEqual(result.as_dict()['randomized'], not isinstance(obj, ScottishSTV))
            self.assertEqual(result.as_dict()['complete'], True)
            self.assertEqual(result.as_dict()['empty_ballot_count'], 3)
        except AttributeError:
            import pdb; pdb.set_trace()

    def test_incomplete_result(self):
        obj = _incomplete_result_fixture(self._cut)
        result = obj.calculate()
        self.assertEqual(result.as_dict()['randomized'], False)
        self.assertEqual(result.as_dict()['complete'], False)

    def test_tie_break_that_breaks(self):
        obj = _tie_break_that_breaks(self._cut)
        result = obj.calculate()
        self.assertEqual(result.as_dict()['randomized'], True)
        self.assertEqual(result.as_dict()['complete'], True)
        self.assertEqual(obj.complete, True)

    def test_multiple_quota_tiebreak(self):
        poll = self._cut(seats=4, candidates=['one', 'two', 'three', 'four', 'five', 'six'])
        poll.add_ballot(['one', 'three'])
        poll.add_ballot(['two', 'four'])
        poll.add_ballot(['five', 'six'])
        result = poll.calculate()
        self.assertTrue(result.complete)

    def test_exceptions(self):
        from stvpoll.exceptions import STVException
        from stvpoll.exceptions import CandidateDoesNotExist
        with self.assertRaises(STVException):
            self._cut(seats=3, candidates=['one', 'two'])
        with self.assertRaises(CandidateDoesNotExist):
            obj = self._cut(seats=3, candidates=['one', 'two', 'three'])
            obj.add_ballot(['one', 'four'])

    def test_randomization_disabled(self):
        poll = self._cut(seats=2, candidates=['one', 'two', 'three'], random_in_tiebreaks=False, pedantic_order=True)
        poll.add_ballot(['one', 'two'], 2)
        poll.add_ballot(['two', 'one'], 2)
        poll.add_ballot(['three'], 1)
        result = poll.calculate()
        self.assertEqual(result.complete, not isinstance(poll, ScottishSTV))

    def test_pedantic_order(self):
        poll = self._cut(seats=2, candidates=['one', 'two', 'three'], random_in_tiebreaks=False)
        poll.add_ballot(['one', 'two'], 2)
        poll.add_ballot(['two', 'one'], 2)
        poll.add_ballot(['three'], 1)
        result = poll.calculate()
        self.assertEqual(result.complete, True)

    def test_bad_config(self):
        from stvpoll.exceptions import STVException
        self.assertRaises(STVException, self._cut, seats=4, candidates=['one', 'two', 'three'])


class CPOSTVTests(ScottishSTVTests):
    wiki_cpo_results = {'Carter', 'Andrea', 'Delilah'}

    @property
    def _cut(self):
        return CPO_STV

    def test_all_wins(self):
        poll = self._cut(seats=2, candidates=['one', 'two'])
        poll.calculate()
        self.assertIs(poll.complete, True)

    def test_possible_combinations(self):
        self.assertEqual(CPO_STV.possible_combinations(5, 2), 10)


class ScottishElectionTests(unittest.TestCase):
    ward_winners = (
        {'Kevin  LANG', 'Louise YOUNG', 'Graham HUTCHISON', 'Norrie WORK'},
        {'Graeme BRUCE', 'Neil GARDINER', 'Ricky HENDERSON', 'Susan WEBBER'},
        {'Robert Christopher ALDRIDGE', 'Claire BRIDGMAN', 'Mark BROWN'},
        {'Eleanor BIRD', 'Jim CAMPBELL', 'Cammy DAY', 'George GORDON'},
        {'Gavin BARRIE', 'Max MITCHELL', 'Hal OSLER', 'Iain  WHYTE'},
        {'Scott DOUGLAS', 'Gillian GLOYER', 'Frank ROSS'},
        {'Denis DIXON', 'Catherine FULLERTON', 'Ashley GRACZYK', 'Donald WILSON'},
        {'Scott ARTHUR', 'Phil DOGGART', 'Jason RUST'},
        {'Gavin CORBETT', 'Andrew JOHNSTON', 'David KEY'},
        {'Nick COOK', 'Melanie MAIN', 'Neil ROSS', 'Mandy WATT'},
        {'Karen DORAN', 'Claire MILLER', 'Jo MOWAT', 'Alasdair RANKIN'},
        {'Marion DONALDSON', 'Amy MCNEESE-MECHAN', 'Susan RAE', 'Lewis RITCHIE'},
        {'Chas BOOTH', 'Adam MCVEY', 'Gordon John MUNRO'},
        {'Ian CAMPBELL', 'Joan GRIFFITHS', 'John MCLELLAN', 'Alex STANIFORTH'},
        {'Steve BURGESS', 'Alison DICKIE', 'Ian PERRY', 'Cameron ROSE'},
        {'Lezley Marion CAMERON', 'Derek HOWIE', 'Lesley MACINNES', 'Stephanie SMITH'},
        {'KATE CAMPBELL', 'MARY CAMPBELL', 'Maureen CHILD', 'Callum LAIDLAW'},
    )

    @property
    def _cut(self):
        # type: () -> Type[STVPollBase]
        return ScottishSTV

    def test_all(self):
        election_dir = 'stvpoll/testdata/scottish_election_data/'
        for f in os.listdir(election_dir):
            ballots = []
            candidates = []
            with open(election_dir + f) as edata:
                standing, winners = map(int, edata.readline().strip().split(' '))
                while True:
                    line = edata.readline().strip().split(' ')
                    if line[0] == '0':
                        break
                    count = int(line.pop(0))
                    line.pop()
                    ballots.append((map(int, line), count))
                for i in range(standing):
                    candidates.append(edata.readline().strip()[1:-1])

            poll = ScottishSTV(winners, candidates)
            for b in ballots:
                poll.add_ballot([candidates[i-1] for i in b[0]], b[1])
            result = poll.calculate()
            ward_number = int(f.split('_')[1])
            self.assertEqual(result.elected_as_set(), self.ward_winners[ward_number-1])


# class CPOElectionTests(ScottishElectionTests):
#
#     @property
#     def _cut(self):
#         return CPO_STV


if __name__ == "__main__":
    unittest.main()
