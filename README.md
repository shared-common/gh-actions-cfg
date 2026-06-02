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
`https://gitlab.com/kalilinux` hierarchy into the relative namespace
`kalilinux`, which the workflow prefixes at runtime with
`GL_GROUP_TOP_GLAB_OWNER`.

## Debian

`glab-groups-debian/` is generated from the current public Salsa top-level group
catalog and sharded into `namespaces-*.json` files. Each entry maps the source
namespace into a relative `debian/...` target path, which the workflow prefixes
at runtime with `GL_GROUP_TOP_GLAB_OWNER`.
