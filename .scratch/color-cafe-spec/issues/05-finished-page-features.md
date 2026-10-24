# Finished page: gallery, export, surprises, print

Type: grilling
Status: resolved
Blocked by: 

## Question

Reference: docs/reference/happy-color/studio-completed.png (completed tab with square thumbnails and check badges; Save progress; replay video).

Updated 2026-10-23: Kandy showed a Happy Color finished page (Google Photos link) and named the **replay video** as a must: the app records the order regions are coloured and plays it back as a time-lapse that can be saved and shared. Our save state is {regionId: colour}; adding fill order makes the replay cheap, and canvas + MediaRecorder (or a server-side render) can export it as a video file.

What happens when a page is finished? Candidates: save progress and keep a 'my gallery' on the device; export the coloured page as PNG; small surprise animations on completion (full version only, like Puzzle Parlor's easter eggs); print the blank page. Decide which are in v1, which are later, and which are out.

## Answer

Decided 2026-10-24 (build kickoff): v1 ships My Studio (in-progress / completed tabs, thumbnails, device save) and a finished-page view. Replay video and PNG export are deferred to v1.1 (Kandy did not select them for v1); the app records fill order from day one so replay can be added without migration. Print deferred.
