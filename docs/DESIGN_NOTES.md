# Design fidelity notes

## How the Figma file was used

The supplied `.fig` file is a ZIP holding Figma's binary "kiwi" format, not an image. It was decoded with the open-source `kiwi-schema` library (25,708 nodes), and each screen was re-rendered to a PNG with a small custom renderer. That renderer expands component instances, overrides and component properties, draws vector paths, and screenshots the result with Playwright. That made it possible to read **exact** values instead of guessing from a thumbnail:

| Token | Value from the file | Where used |
|---|---|---|
| App font | Lato (Regular / SemiBold / Bold) | All app text (`next/font`, self-hosted) |
| Control font | Roboto 14/500, letter-spacing 0.4 (buttons); Roboto 12 captions | MUI buttons, captions, chips |
| Page background | `#F2F2F2` | Page |
| Contained button / name links | `#4081DD` | Primary colour, candidate names |
| Outlined button | `#2196F3`, border 50% | "Add candidate", "Cancel" |
| Table header | `#F6F6F6`, bottom border `#CCCCCC`, 48 px | Table head |
| Row | 42 px, bottom border `#EEEEEE`; selected `#E3F2FD` | Table body |
| Status chips | Read `#E8F5E9`/`#2E7D32` + check · Failed `#FEEBEE`/`#C62828` + error · Sent `#E3F2FD`/`#1565C0` | `StatusChip` |
| Side panel | 660 px, shadow `-2px 0 12px rgba(0,0,0,.16)`, backdrop `rgba(0,0,0,.12)`, 40 px padding, 96 px footer | Send Message, Communication history |
| Recipient chips | `#ECEFF1`, 32 px, Roboto 13 | Send Message |
| Success toast | `#EDF7ED` / `#1E4620`, Roboto 16/500 | Notifications |
| Empty-state illustration | Vector group "Interview", exported to `public/empty-state.svg` | Empty list, empty history |

## Screen-by-screen mapping

| Figma flow (frames) | Implemented as |
|---|---|
| Adding a candidate (5 frames) | `AddCandidateDialog`: title "Add Candidate", fields *Candidate Name\**, *Mobile Number\**, *Email\**; primary button disabled until all fields are filled; toast "‹Name› added successfully"; new row appears at the top |
| Empty state | `EmptyState`: "No candidates added / When you add a candidate, they will appear here." |
| Deleting a candidate (4) | `DeleteCandidatesDialog`, with the designer's copy including the candidate's name; toast "Candidate deleted successfully" |
| Deleting multiple candidates (4) | Different copy for many ("Are you sure you want to delete 5 Candidates?… with these candidates"); toast "5 Candidates deleted successfully" |
| Sending message to one candidate (5) | `SendMessageDrawer`: "1 Recipient", resizable text area (dev note), toast "Message sent to 1 candidate" (shown with the name) |
| Sending to multiple candidates (6) + overflow | Recipient chips limited to **two lines, then "+ n"** (dev note), measured at runtime |
| Viewing communication history (3) | Names have an **underline hover** and open the drawer (dev note); history is **newest first** (dev note); header with Candidate ID, name, phone, email |
| No communication history (3) | "No communication history / You have not communicated with this candidate yet…" |

Every dev note in the file is implemented: name hover and drawer; newest first; resizable text area; chips on two lines then "+n"; the name appears in the delete copy; different copy for multiple deletes.

## Deliberate deviations (and why)

| Deviation | Reason |
|---|---|
| Status labels are capitalised (`Read` rather than `read`) | The design mixes "read" and "Sent"; consistency |
| Extra statuses: Queued, Sending, Retrying, Delivered, Scheduled, Cancelled | The assignment requires tracking delivery accurately; never show "Sent/Delivered" before it's true |
| Success toast says **"Message sent to N candidates"** only when every recipient was accepted; otherwise a warning "Message sent to 3 of 5 candidates. 2 failed." with **View details** | The design only shows the happy path; the assignment requires clear per-candidate results |
| New "Delivery results" dialog | Per-recipient outcomes and retries for bulk sends (not in the design) |
| Failure explanations, Retry/Cancel, and an expandable timeline in history | Required by the assignment; styled with MUI Alerts in the design's palette |
| "Send message" button inside the history panel | Lets recruiters go from history straight to messaging that candidate |
| Template picker, variable chips, "Schedule for later", "Send via" (SMS/Email) in the Send panel | Bonus features; placed between recipients and message so the designed layout is preserved |
| Provider status pill next to the title | Bonus "provider health"; the header had spare space |
| Content card has an 8 px margin on all sides | The design's card is flush left with an 8 px gap on the right, which reads as a leftover from a removed sidebar |
| Column header filter icons open sort/filter menus | The design shows the icons without behaviour; they now do something useful |
| Lato SemiBold renders as Bold | Google Fonts only serves Lato 400/700; self-hosting a non-Google SemiBold wasn't worth the licensing and maintenance cost |
| "Moblie Number" typo fixed to "Mobile Number" | Typo in the design |
