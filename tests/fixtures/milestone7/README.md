# Milestone 7 report fixtures

`draft-compatible-report.json` is a known-answer fixture for the provisional
M7 compatibility-report JSON projection. Slice 4 internal review advanced the
draft to revision 2 after removing machine-local artifact paths from the wire
shape; the fixture pins those revised bytes. The stable report schema/version
remains intentionally unfrozen until the hardened boundary passes its
authoritative gate and the remaining Slice 4 schema checkpoint is complete.
