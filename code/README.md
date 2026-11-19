# Code Layout

This folder contains research code organized as plain Python module folders.
It is not an installable package layout.

- `chronos_fpa/`: current Chronos branching/FPA pipeline.

Chronos modules are split into `core`, `data`, `metrics`, `pipeline`, `runtime`,
`analysis` and `visualization`. Scripts add `chronos_fpa/` then import its
`bootstrap.py` to configure the functional folders. No installable research
package is introduced. Earlier TimesFM code remains in the original workspace.
