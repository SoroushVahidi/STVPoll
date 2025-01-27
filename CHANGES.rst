Changes
=======


0.3.0 (dev)
-----------

- Introduce *pedantic_order=False*, to avoid incomplete results when randomization can not affect who is elected.


0.2.3 (dev)
-----------

- Fixed bug where votes were discarded in select_multiple.
- Scottish STV: Select proposals in order of most votes, when there is no more competition.


0.2.2 (dev)
-----------

- Fixed bug with tie in first round on Scottish STV.
- Fixed bug in quota selection of all seats in CPO.


0.2.1 (dev)
-----------

- Unreleased


0.2.0 (2018-05-23)
------------------

- Fixed bug in deciding which vote to transfer first when multiple elected in Scottish STV. [schyffel] [robinharms]
- Scottish STV: Resolve ties so that winners are always in correct ranking order (extreme case). [schyffel]
- Now works on Python 3. [schyffel]
- Test coverage 100 %. [schyffel]


0.1.4 (2018-05-12)
------------------

- Fixed a situation where primary_candidate in rounds didn't exist. [schyffel] [robinharms]


0.1.3 (2018-03-22)
------------------

- Excluded empty ballots, so that they do not affect the quota. [schyffel]


0.1.2 (2017-11-24)
------------------

- Fixed exception on empty ballots. [schyffel]


0.1.1 (2017-11-24)
------------------

- Fixed case where randomization caused an exception. [schyffel]


0.1.0 (2017-11-03)
------------------

-  Initial version
