# ooo-test

Brownfield playground for [ouroboros](https://github.com/Q00/ouroboros).

This repo is registered as a brownfield default so `ooo interview` /
`ooo seed` / `ooo run` carry this directory's context.

## Layout

- `.ouroboros/mechanical.toml` — Stage 1 evaluation contract (lint/build/test/coverage commands).

## Usage

```sh
ooo brownfield         # verify registration
ooo interview "..."    # Socratic requirements refinement
ooo seed               # crystallize immutable spec
ooo run seed.yaml      # execute via Double Diamond
ooo evaluate           # 3-stage gate (mechanical / semantic / consensus)
```