# m1-room-changes
Static GitHub Pages site for Sorbonne PHYSIQUE M1 room changes and cancellations.

Cron every four hours downloads the public Google ICS feed, builds a candidate
`index.html`, and compares embedded page data against the current page. Only
when courses, events, or vacation weeks change does it commit and push the
submodule, then commit and push the parent site so GitHub Pages rebuilds it.

Install: `./cron.sh install`
Remove: `./cron.sh remove`
Force a rebuild and publish: `./publish.sh`

Set `M1_SITE_ROOT` when the parent site is elsewhere (default:
`/mnt/win/Code/corvin.sydow.ch`).

`settings.toml` contains the complete current semester course list, baseline
rooms, and the ICS feed URL. Edit `template.html` for page layout and styling.

## Git hooks

Pushes are handled by the parent repo's `install-submodule-git-hooks.sh`, which
installs a `post-commit` hook in each submodule. Re-run that script from the
parent repo root after cloning or if the parent directory moves. Do not edit
`.git/hooks/post-commit` in this submodule directly.

## Development

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -v
python3 build_static_site.py path/to/basic.ics /tmp/index.html
```

The local Akonadi report lives in the separate sorbonne-calendar-sync repo.
