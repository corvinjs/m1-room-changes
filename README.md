# m1-room-changes
Static GitHub Pages site for Sorbonne PHYSIQUE M1 room changes and cancellations.

Cron every four hours downloads the public Google ICS feed, builds a candidate
`index.html`, and uses `git diff` against the current page to decide whether
anything beyond the generated-at timestamp changed. Only then does it commit
and push the submodule, then commit and push the parent site so GitHub Pages
rebuilds it.

Install: `./cron.sh install`
Remove: `./cron.sh remove`
Force a rebuild and publish: `./publish.sh`

Set `M1_SITE_ROOT` when the parent site is elsewhere (default:
`/mnt/win/Code/corvin.sydow.ch`).

`settings.toml` contains the complete current semester course list and baseline
rooms. Edit `template.html` for page layout and styling.

The local Akonadi report lives in the separate sorbonne-calendar-sync repo.
