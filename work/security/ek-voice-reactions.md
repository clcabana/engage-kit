# Threat model: ek-voice-reactions (static review, 2026-10-26)

- **Assets:** voice clips (base64 + mime + seconds + feature/target) in `localStorage['ek:<slug>']`; the consent flag `ek:consent`; the browser's per-origin microphone grant; the review-row blob URL before Keep.
- **Actors:** recording resident; bystanders and minors in mic range; the next visitor on the same phone (plays every clip via timeline memories); a hostile visitor (tampers with storage, records others); the team collecting the device; the client; the model that wrote the code.
- **Entry points:** microphone stream (`getUserMedia`, build.py:72); recorder mime string (build.py:92, trusted only after the `^audio/[\w.+-]+$` test in ek-timeline render, build.py:269); stored JSON (shell template.html:144 shape filter; value is not inspected); the bar context `EK.ctx()` written into `target`.
- **Spoof:** n/a locally. No identity; a clip is as anonymous as its voice. Any visitor can record "as" anyone, which is the design.
- **Tamper:** a same-origin page or devtools can rewrite `ek:<slug>`; render validates mime and base64 charset so the worst case is a non-playing `<audio>`. Duplicate Keep taps (build.py:92, no disable) can store the same clip twice.
- **Repudiate:** no log; a resident cannot prove a clip was or was not theirs. Acceptable for anonymous engagement; the team's table script should not treat clips as attributed.
- **Disclose:** every clip on the phone is playable by the next visitor and by whoever picks the phone up (ek-timeline render, no per-clip delete, Remove all wipes everyone's). Consent card never says this. Bystander and child voices can be captured; "Don't record other people" is the only guard.
- **Deny:** `save()` swallows QuotaExceededError (template.html:145) and `react()` still returns the record (:157), so the guard at build.py:93-94 can pass, the toast says "kept", the list and counts show it, and the clip is gone on reload. The guard also counts only this slug, while the 5 MB quota is per origin (demo + output on one GitHub Pages host share it).
- **Elevate:** none. No network calls, no eval/innerHTML, no credentials; build.py reads and writes `--out` only (build.py:128-134).
- **Minors:** drop-in tables are open to children; flag to the team (parent present, or do not record).
- **Hosting:** `getUserMedia` needs a secure context; HTTPS (GitHub Pages) or localhost works, a LAN `http://192.168…` server silently falls back to typed. file:// works in Chrome/Firefox, not reliably in Safari. Test on the actual table phones.
