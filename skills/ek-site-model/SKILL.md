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

## Markup it writes
```html
<section data-feature="model" data-title="The model" hidden>
  <h2>The site in 3D</h2>
  <p class="lede">Turn the model, move the sun, stand at each building and look out. Then say whether its spot works for you, and type why.</p>
  <div class="sm ek-stage">
    <div class="sm-view"> <canvas tabindex="0"> <div class="sm-labels"> <details class="sm-ovl sm-viewbox"> trees · labels · shadows · sun az/alt </details> <div class="sm-fallback" hidden> </div>
    <div class="sm-card"> <small>about</small> <div class="sm-chips">one chip per building</div>
      <div class="sm-sel" hidden> name · view bearing · [The spot works] [It should move] · [Say why] [Stand here] [Back to overview] · notes </div>
      <div class="sm-none"> [Overview] hint </div>
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
  none is given); drag turns the head; **Back to overview** returns.
- Fallback: no three.js or no WebGL → a message, and the chips, votes and notes still work.
- Tour: three steps (turn; pick the first building; stand there).

## Extension point
`EK.feature.model` = `{buildings, select(label), selected(), overview, fallback, render(), rebuild(), renderer,
camera, canvas, view, stand(label), standAt(bearingDeg, label?)}` plus, for augments such as `ek-model-pins`:
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
