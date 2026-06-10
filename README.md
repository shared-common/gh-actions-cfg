# gh-actions-cfg

## Shared group-mirror configs

The Perl/Python group mirror flow consumes per-wrapper config directories:

- `glab-groups-android/`
- `glab-groups-chromium/`
- `glab-groups-freedesktop/`
- `glab-groups-debian/`
- `glab-groups-gnome/`
- `glab-groups-hashicorp/`
- `glab-groups-kali/`
- `glab-groups-kde/`
- `glab-groups-microsoft/`
- `glab-groups-nvidia/`
- `glab-groups-openai/`
- `glab-groups-projects/`
- `glab-groups-small/`

Config directories can use JSON or YAML files keyed by `kind`:

- `glab-groups/defaults`
- `glab-groups/namespaces`
- `glab-groups/projects`
- `glab-groups/project-exclusions`

Each namespace-based wrapper config directory also carries:

- `exclude.yml`: YAML object with `kind: glab-groups/project-exclusions`
- `projects.yml`: YAML object with `kind: glab-groups/projects`

`projects.yml` is authoritative. When one of its entries resolves to the same
target project path that namespace discovery would produce, the shared runtime
skips that namespace-discovered project and uses the explicit `projects.yml`
entry instead.

Each `projects.yml` item may set only the fields it wants to override. Along
with `source_project_url` and `target_group_path`, supported optional policy
fields include `allow_blob_rewrite`, `force_lfs`, `git_timeout_seconds`,
`mirror_pristine_tar`, `read_retry_attempts`,
`read_retry_backoff_seconds`, `retry_attempts`,
`retry_backoff_seconds`, `size_limit_bytes`, `max_blob_bytes`,
`additional_branches`, `additional_tags`, and
`target_branches_protect`.

The `defaults` files keep the common run policy explicit:

- `batch_size`: target-group-aware batch sizing that never splits one target subgroup across multiple mirror jobs
- `max_parallel`: maximum concurrent GitHub Actions prepare and mirror shards for that wrapper
- `mirror_pristine_tar`: mirrors detected `pristine-tar` branches or tags
- `additional_branches`: user-managed extra branch names to mirror each run
- `additional_tags`: user-managed extra tag names to mirror each run
- `size_limit_bytes`: selected-ref repository budget, defaulting to 9 GiB
- `max_blob_bytes`: blob limit, defaulting to 100 MiB
- `retry_attempts` and `retry_backoff_seconds`: bounded retry policy

Each namespace entry may also set:

- `target_owner_path`: checked-in target owner/group path for that specific namespace entry

Each namespace or explicit project entry may also set:

- `target_branches_protect`: target branch names to protect after bootstrap

Checked-in target GitLab group IDs are intentionally unsupported. The shared
runtime resolves target groups from `target_owner_path` plus
`target_namespace_path` or `target_group_path` at run time and keeps the
resolved IDs only in the in-memory mirror-job cache.

Target visibility is intentionally absent from these configs. The shared mirror
workflow does not set group or project visibility on GitLab targets; configure
visibility on the target owner/group outside scheduled mirror runs.

## Kali

`glab-groups-kali/namespaces.json` mirrors the full public
`https://gitlab.com/kalilinux` hierarchy into the relative namespace
`kalilinux`, which the workflow prefixes at runtime with
`target_owner_path`.

## Debian

`glab-groups-debian/namespaces.json` points at the public root of
`https://salsa.debian.org`. The shared runtime expands that source into the
current public top-level groups and maps them beneath the relative target
prefix `debian/`.

## Freedesktop

`glab-groups-freedesktop/namespaces.json` points at the public root of
`https://gitlab.freedesktop.org`. The shared runtime expands that source into
the current public top-level groups and maps them beneath the relative target
prefix `freedesktop/`.

## Small

`glab-groups-small/namespaces.json` mirrors a curated mixed-source set:

- public GitHub organizations such as `https://github.com/labwc`
- public GitLab groups such as `https://gitlab.com/xanmod`

Each entry maps into a relative target namespace path beneath
`target_owner_path`. GitHub-source entries authenticate through the shared
GitHub App secrets `GH_ORG_READ_APP_ID` and `GH_ORG_READ_APP_PEM`.

`glab-groups-small/projects.yml` carries the full explicit Netfilter project
set from the current `netfilter.org/projects/` listing. Those entries mirror
directly from project clone URLs instead of scraping the root index, because
`https://git.netfilter.org` is now fronted by an anti-bot challenge that makes
root discovery unreliable in CI.

## OpenAI

`glab-groups-openai/namespaces.json` points at the public root of
`https://github.com/openai`. The shared runtime mirrors the current public
organization repositories beneath the relative target prefix `openai/`.

## HashiCorp

`glab-groups-hashicorp/namespaces.json` points at the public root of
`https://github.com/hashicorp`. The shared runtime mirrors the current public
organization repositories beneath the relative target prefix `hashicorp/`.

## Microsoft

`glab-groups-microsoft/namespaces.json` points at the public root of
`https://github.com/microsoft`. The shared runtime mirrors the current public
organization repositories beneath the relative target prefix `microsoft/`.

## NVIDIA

`glab-groups-nvidia/namespaces.json` points at the public root of
`https://github.com/nvidia`. The shared runtime mirrors the current public
organization repositories beneath the relative target prefix `nvidia/`.

## Android

`glab-groups-android/namespaces.json` points at the public root of
`https://android.googlesource.com`. The shared runtime scrapes the Gitiles root
index, preserves nested repository paths such as `platform/...`, and maps them
beneath the relative target prefix `android/`.

## Chromium

`glab-groups-chromium/namespaces.json` points at the public root of
`https://chromium.googlesource.com`. The shared runtime scrapes the Gitiles
root index, preserves nested repository paths such as `chromium/...`, and maps
them beneath the relative target prefix `chromium/`.

## KDE

`glab-groups-kde/namespaces.json` points at the public root of
`https://invent.kde.org`. The shared runtime expands that source into the
current public top-level groups and maps them beneath the relative target prefix
`kde/`.

## GNOME

`glab-groups-gnome/namespaces.json` points at the public root of
`https://gitlab.gnome.org`. The shared runtime expands that source into the
current public top-level groups and maps them beneath the relative target
prefix `gnome/`.

## Explicit projects

`glab-groups-projects/projects.yml` carries explicit single-project mirrors
whose destination is built as `<target_group_path>/<name>`. Those entries do
not derive target namespace segments from the source repository URL.
