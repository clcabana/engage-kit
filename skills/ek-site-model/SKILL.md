---
name: ek-site-model
description: Add the design team's own 3D site model to an Engage Kit tool — terrain, water, trees, existing and proposed buildings exported from a Rhino .3dm file — as a viewer with Massing Studio's interaction (orbit, pan, pinch, sun with shadows, floating labels, eye level at each building), where every proposed building is a reaction target. Use whenever the team has a Rhino site model, the user asks to "put the model in the tool", wants people to walk the site in 3D, stand at a building, or react to where things are placed; not for options drawn as boxes from a deck (that is ek-site-massing-3d).
---

# Site model

Two scripts. `export_3dm.py` turns a Rhino file into a compact viewer JSON with `rhino3dm` (no Rhino
needed): it uses the render meshes Rhino saved with the breps, bakes block instances to world
coordinates one mesh per building, reduces tree meshes to one record per tree, and samples curves to
polylines. `build.py` writes the viewer into the shell's `model` slot ("The model").

## Run it
```
python -m pip install -r skills/ek-site-model/requirements.txt   # rhino3dm, once
python skills/ek-site-model/export_3dm.py --in <site.3dm> --out work/model.json \
       --terrain "3D Site::Surface" --water "3D Site::Waterbody" --trees "3D Site::NEW" \
       --existing "3D Site::NEW" --buildings "Massings" --curves "3D Site::Site Features" \
       --label "Hermitage Single=Hermitage cabin" --label "Chaplain Residence=Chaplain's House"
python skills/ek-site-model/build.py --brief work/brief.json --model model.json --out output/index.html --root work
```
Layer names are the team's; pass the ones the file uses (`::` separates parents). Hidden layers and
hidden sub-layers inside blocks stay out. The exporter prints what it found (vertices per mesh, buildings
with labels, trees, curves) and warns about breps without render meshes. Keep the `.3dm` and the exported
JSON out of the public repo; the JSON is embedded into the built page.

Brief fields read by `build.py`: `site.views[]` = `{building, bearing_deg, source_slide}` from the deck's
views page; a building whose label matches gets "Stand here" looking that way and the bearing in its card.

`site.model_views[]` (optional, at most 8) = the set views in the card's "Views" row. Each entry is one of
```json
{"name": "Overview", "kind": "overview"}
{"name": "From the river", "kind": "orbit", "orbit": {"th": 1.25, "ph": 1.06, "r": 0.8, "pan": [0, 0]}}
{"name": "At the hall", "kind": "stand", "building": "Hall"}
{"name": "Hall door", "kind": "bearing", "bearing_deg": 250, "building": "Rooms wing"}
```
with an optional one-line `"text"` shown under the row. `th`/`ph` are the orbit angles in radians, `r` the zoom
(1 = the overview distance), `pan` metres east / south of the model's centre; `bearing` without `building` stands
at the model's centre. The build checks finite numbers, known building labels and names of at most 40
characters; a bad entry is warned and skipped, and entries past 8 are dropped. **When the field is present the
row is exactly that list**; when absent the build makes at most five defaults with no near-duplicates: Overview,
From the south, From above, then at most two "At <building>" views, one per building. Buildings with a
`site.views[]` bearing come first (in that order), as a bearing view named "At <building>" with the presentation's
bearing and slide in its text; then modelled buildings without one, as a stand view.

**Views file.** The admin portal's "Save this view" hands out `model-views.json`: the full array for
`site.model_views` (the brief's views, or the defaults, plus the session's new ones). Nobody edits the brief to
use it:
```
python skills/ek-site-model/build.py --brief work/brief.json --model model.json --out output/index.html --root work --views model-views.json
```
or set `site.model_views_file: "model-views.json"` in the brief (what `chain.py` builds pick up). Either path is
relative to `--root` and must resolve under it (absolute, drive, UNC and `..`-escaping paths are refused); the
file is a JSON array (at most 200 KB) validated entry by entry exactly like `site.model_views`, and it replaces
that field. Precedence: `--views`, then `site.model_views_file`, then `site.model_views`, then the defaults. A bad
`--views` file stops the build with nothing written; a bad `site.model_views_file` is warned and the build falls
back. The build's JSON line says `views_from`.

## Markup it writes
```html
<section data-feature="model" data-title="The model" hidden>
  <h2>The site in 3D</h2>
  <p class="lede">Turn the model, move the sun, stand at each building and look out. Then say whether its spot works for you, and type why.</p>
  <div class="sm ek-stage">
    <div class="sm-view"> <canvas tabindex="0"> <div class="sm-labels"> <details class="sm-ovl sm-viewbox"> trees · labels · shadows · sun az/alt </details> <div class="sm-fallback" hidden> </div>
    <div class="sm-card">
      <div class="sm-views" id="smViews" hidden> kicker "Views" · [‹ Previous view] <div class="sm-vlist" role="toolbar"> one pill per view </div> [Next view ›] · text · [Save this view] (admin) · <form class="sm-vout"> name · [Save the view] · saved list · [Download views file] [Copy] </form> </div>
      <small>about</small> <div class="sm-chips">one chip per building</div>
      <div class="sm-sel" hidden> name · view bearing · [The spot works] [It should move] · [Say why] [Stand here] [Back to overview] · notes </div>
      <div class="sm-none"> [Overview] hint </div>   <!-- the Overview button hides while the Views row (whose overview chip does the same) shows -->
      <div class="sm-slot" data-slot="pins" id="smSlot"></div>   <!-- empty; ek-model-pins mounts here; hidden while a building is selected -->
    </div>
  </div>
</section>
```

## Behaviour
- **Interaction** (from Massing Studio): drag orbits, right-drag / shift-drag / two fingers pan, pinch or
  scroll (canvas focused) zooms, double-click or `0` resets; arrows orbit, `+`/`-` zoom. Sun azimuth and
  altitude sliders move a shadow-casting light; shadows, trees and labels can be switched off. Light and
  dark palettes are matte greys from the project tokens; the proposed buildings are the only colour
  (`--plan`, selected `--marker`); trees are a trunk and a crown drawn per record with instancing.
- **Labels** float over each proposed building and follow the camera.
- **Tap a building** (in the model or its chip) to select it: the card names it, quotes the view bearing the
  presentation gives it, and sets `EK.context('model', <label>, …)`. **The spot works / It should move**
  records `{feature:'model', target:<label>, kind:'vote', value:'keep'|'move'}` (one per building per
  device, tap again to remove; the new choice is stored before the old is removed). **Say why** puts the
  cursor in the shared bar (voice if registered). Notes and clips for the building list in the card.
- **Stand here** puts the camera 1.6 m above the building's floor, looking along its bearing (south when
  none is given); drag turns the head; **Back to overview** returns. A tree trunk right in front of the eye fills
  the frame, so in stand / bearing positioning the point just outside the facade is nudged sideways along the
  facade (0, then ±0.5 m steps up to ±3 m, nearest first) to the first point more than 1.5 m from every tree
  record's trunk (`[x, y, z, h, r]`, horizontal distance); when none qualifies the original point is kept.
- **Views row** (top of the card, in overview and with a building selected): one pill per set view. On a phone
  it is one horizontally scrolling row with 44 px Previous / Next buttons at its ends (they wrap around); from
  900 px it wraps and the steppers go. Tapping a view eases the camera there in about 300 ms (instant under
  reduced motion), marks it `aria-pressed` and, for overview / orbit / bearing views, sets
  `EK.context('model', <view name>, '— what do you think of this view?')`; a stand view selects its building and
  keeps that building's context. Arrow keys / Home / End move between pills. Dragging, zooming or a building
  chip clears the pressed view; reset / double-click / Overview marks the overview view. The row is hidden when
  there is one view or none in the user portal (nothing to step through). While the row shows and has an
  overview view, the card's separate Overview button is hidden (the row's first chip does the same); with no
  row (one view, or the fallback) the button stays.
- **Admin capture** (`PROJECT.portal === "admin"` only): "Save this view" freezes the current camera (the orbit, or
  the standing building and bearing) and asks for a name in an inline field; **Save the view** adds it to the row
  for this session (a name the brief already uses is refused) and lists the session's saved views by name. Under
  the list: **Download views file** (primary) downloads `model-views.json`, the full array for
  `site.model_views` (every view in the row, `session` flags removed), and **Copy** (secondary) copies the same
  text, with "Send this file to whoever builds the tool, or ask the kit's assistant to add these views." The
  builder runs `build.py --views model-views.json` or sets `site.model_views_file` (above). The page writes
  nothing: new views last until a reload. The row always shows in the admin portal, even with one view, so a
  first view can be saved.
- Fallback: no three.js or no WebGL → a message, and the chips, votes and notes still work (the Views row hides).
- Tour: three steps (turn; pick the first building; stand there).

## Extension point
`EK.feature.model` = `{buildings, select(label), selected(), overview, fallback, render(), rebuild(), renderer,
camera, canvas, view, stand(label), standAt(bearingDeg, label?), views(), goView(name)}` plus, for augments such as `ek-model-pins`:
- `scene` — the three.js scene (null in fallback). Rebuilds (theme, shadows) replace only the model's own group,
  so objects an augment adds to `scene` survive them.
- `ground()` — the current terrain, water and existing meshes (`userData.kind` = `terrain|water|existing`).
- `onPick(fn)` — `fn(hit, raycaster, event)` runs on every tap before the default building select. `hit` is the
  first surface the ray meets among buildings and ground, `{point:[x,y,z], distance, building|null, kind, object}`,
  or null. Returning `true` means handled (no building select). The default select still raycasts buildings only,
  so its behaviour is unchanged.
- `onRender(fn)` — runs after every frame (after the building labels), for an augment's own projected labels.
- `project([x,y,z])` — `{x, y, on}` in view pixels; `on` is the labels' own in-front-and-in-frame test.
- `bbox` `{min:[x,y,z], max:[x,y,z]}` and `span` — the model's extent in metres (copies).
- The card ends with an empty `<div class="sm-slot" data-slot="pins" id="smSlot">` for the augment's controls.
  It shows only in overview: selecting a building hides it (`hidden`), so one way to react is on screen at a time.
- `stand(label)` — selects that building (exact label, else case-insensitive) and runs Stand here (outside the
  facade on its bearing, south when none). `standAt(bearingDeg, label?)` — stands at the named building, or at the
  model's centre 1.6 m above the terrain when no label is given, looking along `bearingDeg` (degrees from north).
  Both call `EK.show('model')` first when another section is showing (the stage sizes on `ek:show`) and render
  again after 80 ms, so they work straight from a link in another section. Return `true` when the camera moved,
  `false` for an unknown label, a non-numeric bearing or the fallback (the section still shows).
- `views()` — the set views as the brief would write them (`{name, kind, orbit?|building?|bearing_deg?, text?}`;
  admin session-only views carry `session: true`). `goView(name)` — shows the model section first (as `stand`
  does) and moves to that view (exact name, else case-insensitive); `true` when the camera moved, `false` for an
  unknown name or the fallback.

## Rules
- The model is the team's working file as exported, and the card says so: what is not modelled is not in
  the tool, and the brief's `to_confirm` lists it. Never add geometry the file does not have.
- Labels are public words (`--label` maps block names to them); a definition placed more than once gets a
  position word (north / middle / south) rather than a number the deck may use differently.
- three.js r128 from cdnjs, pinned with SRI, loaded once per page even when `ek-site-massing-3d` is also
  installed. No other external request.
- Buffers are base64 numbers checked at build time (charset, index type, bbox); labels, bearings and notes
  are rendered with `textContent`. Caps: 12 buildings as targets, 3,000 trees, 400 curves, 6 MB model.
- Keep the page honest about size: the model is embedded; the build prints the byte count.
