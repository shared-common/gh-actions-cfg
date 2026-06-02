# gh-actions-cfg

## Group sync configs

Each `gh-actions-glab-group` group sync config must contain source groups from a
single GitLab host. The group-sync workflow expands every target with one
`GL_BASE_URL` client, so source groups from different hosts must live in
separate config files.

- `gh-actions-glab-group/gl_forks_group.json` is the active GitLab.com group
  config.
- `gh-actions-glab-group/salsa/gl_forks_group.json` is the Salsa group config
  and requires a workflow run configured with `GL_BASE_URL=https://salsa.debian.org`.
