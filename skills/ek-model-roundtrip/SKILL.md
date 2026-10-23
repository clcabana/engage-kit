---
name: ek-model-roundtrip
description: Let visitors download the massing options as open 3D files, change them in their own software (Rhino, SketchUp, Revit, Blender, anything), and upload the result as a response that is placed on the same site and shown beside the architects' version. Use whenever the user wants design feedback to come back as a model, asks for export/import of the 3D, "let people edit the model offline", or a round trip between the engagement tool and modelling software.
---

# Model round-trip

Extends `ek-site-massing-3d`. Requires it.

## Export
- "Download this option" produces a plain-text OBJ (and optionally glTF) generated in the browser from the
  option's blocks, with the site outline and context as separate named groups, metres, Y up, origin at
  the site centre. A README line inside the file says what it is and asks the visitor to keep the site in place.
- In hosts where downloads are inert, show the file in a copyable textarea and a "copy" button.

## Import
- "Upload your version" accepts OBJ, glTF/GLB, STL, SKP is not parsed (ask for OBJ export); size cap 10 MB.
- Parse in the browser with three.js loaders (pinned); place at the site origin; show it on the same
  ground with context, side by side with the original option (two viewports or a toggle).
- Ask one sentence: "What did you change, and why?" Required. Store the model, the sentence, the option
  it responds to, and a thumbnail rendered from the canvas.
- Reaction: `{feature:'massing', target:'option-B', kind:'submission', value:{model:<id>, note, thumb}}`.

## Rules
- Uploads are untrusted content: parse with the loader only, never execute anything from the file,
  cap triangle count, and hand every submission to `qc-security` before it is listed in the gallery.
- Submissions never overwrite an option; they sit beside it and can be voted on like one.
- Device-local until the manifest names a sync target; then submissions go to the shared store with the
  session id, never a name.
