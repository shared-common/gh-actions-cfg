# gh-actions-cfg

## Legacy configs

The historical `gh-actions-glab-group/*` files remain in this repository for the
older Python-based group sync wrappers.

## Shared group-mirror configs

The new Perl/Python group mirror flow consumes per-wrapper config directories:

- `glab-groups-kali/`
- `glab-groups-debian/`

Each directory contains JSON files keyed by `kind`:

- `glab-groups/defaults`
- `glab-groups/namespaces`
- `glab-groups/project-overrides`
- `glab-groups/project-exclusions`

## Kali

`glab-groups-kali/namespaces.json` mirrors the full public
`https://gitlab.com/kalilinux` hierarchy into `glab-forks/kalilinux`.

## Debian

`glab-groups-debian/namespaces.json` is generated from the current public Salsa
top-level group catalog and maps each source namespace into
`glab-forks/debian/...`, with `debian/*` itself rooted directly at
`glab-forks/debian`.
