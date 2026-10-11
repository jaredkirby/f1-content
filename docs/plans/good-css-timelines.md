# Good CSS timeline experiment

## Objective

Improve both existing timelines on `experiment/good-css-timelines` while
preserving their monochrome colors, typography, content and responsive layout.
The user authorized publication after reviewing the local experiment. Both
existing private Sites now have successful new deployments.

## Decisions

- Use [Good CSS](https://good-css.com/) as technique guidance, without installing
  a package or global skill. Read its foundations, interaction, text/media and
  scroll/viewport references.
- Change the shared packaged `f1_pipeline/resources/timeline.css`, consumed by
  both the Sprint page script and Qualifying timeline builder.
- Gate hover by input capability, provide press feedback, enlarge theme hit
  areas without enlarging their visible backgrounds, and make filter hits 44px.
- Keep smooth scrolling opt-in for motion preferences; retain anchor offsets.
- Allow long evidence links and nested grid text to wrap without truncation.
  Keep the existing palette, fonts, headings, video boxes and native disclosures.
- Correct shared theme initialization to restore a valid saved theme. Browser
  inspection found that Qualifying previously reset it to Auto on reload.
- Build ignored local previews by replacing only the shared CSS in retained
  HTML and replacing the shared theme script, preserving each page's extra rules.
  Link existing assets without copying or rerendering media. Keep independent
  Site checkouts untouched during local experimentation.
- Preserve the unrelated `docs/plans/timeline-workflow-site.md` working file.

## Next action

Review the local previews under `runs/good-css-timelines/sprint/index.html` and
`runs/good-css-timelines/qualifying/index.html`. To serve them again:

```sh
.venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory runs/good-css-timelines
```

Visit `/sprint/` or `/qualifying/` on that local server. Each directory also has
`baseline.html`. The private preview helper reads original CSS/JS from HEAD;
after committing, retain the existing previews or adapt the helper to read the
original revision before rebuilding. Both new Site versions are published;
the next acceptance step is the user's review on a real phone.

## Verification

Both previews have no page overflow at 320, 390, 768 and 1280px. At 390px the
before/after body font, H1 size, hero position and layout width match. Expanded
story disclosures fit. Highlight filters show 5/13 and All restores 13. Theme
choice survives reload; keyboard focus retains its 2px outline. Reduced motion
disables smooth scroll, and the Qualifying timeline anchor clears the sticky
header. Both consoles have no warnings/errors. Theme hit regions are 44px with
unchanged visible height; filters are 44px tall. Touch hover capability emulation
was unavailable, so the input-capability gate was inspected in source.

JavaScript syntax, all 157 offline tests, synthetic CLI smoke checks, diff
whitespace and the index guard pass. The shared check was repeated only after
the newly discovered theme defect was fixed. Private receipts and screenshots
are in `runs/good-css-timelines/`. The original Site HEADs, status and HTML hashes
were unchanged through local testing. After explicit publication authorization,
only the tested `dist/index.html` was applied to each independent Site. The
source helper committed, pushed and packaged each exact state; both native
private deployment calls returned `succeeded`. Private deployment receipts
retain the version, deployment, source commit and URL. Sharing remains
owner-private. No event rerun or media copy occurred. Full playback, real phone
and editorial acceptance remain outstanding.
