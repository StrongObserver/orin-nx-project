# Challenge Boundary

## Purpose

Regular gate is the in-domain success story. Challenge sets explain where the
current global-warp EIS model reaches its boundary.

## Boundary Result

| Category | Result | Main attribution |
|---|---|---|
| Running | 1 pass, 1 black-border hard fail | High-frequency motion creates FOV pressure. |
| QuickRotation | 2 black-border hard fails | Fast rotation exceeds crop/FOV budget. |
| Parallax | 2 black-border hard fails | One global transform cannot represent foreground/background depth variation. |
| Crowd | 2 black-border hard fails | Foreground/crowd motion and FOV pressure make global estimation less reliable. |

## How To Say It

```text
The Regular baseline is valid inside its operating envelope. I also evaluated
challenge categories to avoid overclaiming. Running, fast rotation, parallax, and
crowd scenes expose the limits of a single global warp. This motivates future
mesh/RS-aware work, but it is not part of the current Regular baseline claim.
```

## Evidence

```text
docs/challenge_boundary_report_2026-07-18.md
results/challenge_boundary_package_20260718/eval/challenge_boundary_eval.csv
C:\Users\Admin\Videos\orin nx\review\challenge\20260718_challenge_boundary_package\
```
