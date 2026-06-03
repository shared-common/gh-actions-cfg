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

The `defaults.json` files keep the common run policy explicit:

- `batch_size`: 25 repositories per batch
- `mirror_pristine_tar`: mirrors detected `pristine-tar` branches or tags
- `additional_branches`: user-managed extra branch names to mirror each run
- `additional_tags`: user-managed extra tag names to mirror each run
- `size_limit_bytes`: selected-ref repository budget, defaulting to 10 GiB
- `max_blob_bytes`: blob limit, defaulting to 100 MiB
- `retry_attempts` and `retry_backoff_seconds`: bounded retry policy

Target visibility is intentionally absent from these configs. The shared mirror
workflow does not set group or project visibility on GitLab targets; configure
visibility on the target owner/group outside scheduled mirror runs.

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
