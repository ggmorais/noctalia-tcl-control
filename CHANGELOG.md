# Changelog

## 1.1.0

- Group repeated temperature +/− clicks into one cloud command, 800 ms after the
  last click, with immediate local preview.
- Allow further temperature edits during an active temperature request; queue
  only the latest target and keep requests serialized.
- Preserve drafts across background state refreshes. Returning to the existing
  target sends nothing; enforce the existing 16–30 °C limits.
- Flush the chosen temperature when closing the panel; cancel unsent drafts on
  plugin exit/reload or request failure.
- Add 14 fake-host panel behavior tests, run in CI without credentials or hardware.

## 1.0.0

- First public release: TCL Home cloud companion and Noctalia panel, Home shortcut
  and bar widget; English/Portuguese UI; isolated setup; MIT license.
