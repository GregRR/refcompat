# Milestone 6 fixtures

`ucsc-provider-snapshot.json` is a synthetic, redistributable provider snapshot
used to test deterministic UCSC preflight behavior without contacting UCSC.
The database, sequence identities, aliases, source locators, and acquisition
timestamp are fixture values rather than claims about a real UCSC database.

`invalid-hub.txt` is a deliberately incomplete synthetic hub descriptor used only
as a non-reference negative control. RefCompat does not parse or validate it; the
Milestone 6 exit suite uses it to prove that a positive reference-compatibility
result is not a claim that unrelated UCSC hub structure is valid.
