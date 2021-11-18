from __future__ import annotations

from decimal import Decimal
from math import floor
import typing

if typing.TYPE_CHECKING:
    from stvpoll.abcs import STVPoll


# Used in CPO STV
def hagenbach_bischof_quota(poll: STVPoll) -> int:
    return int(floor(Decimal(poll.ballot_count) / (poll.seats + 1)))


# Used in Scottish STV
def droop_quota(poll: STVPoll) -> int:
    return hagenbach_bischof_quota(poll) + 1


# Not used at this time
def hare_quota(poll: STVPoll) -> int:  # pragma: no coverage
    return int(floor(Decimal(poll.ballot_count) / poll.seats))
