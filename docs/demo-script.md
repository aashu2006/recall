# Recall demo script

Two videos from one recording session:

- **Full cut:** 2 min 30 s, 8 scenes
- **Short cut:** 60 s, the same footage with shorter lines

Synthetic data only. The clients are the seeded demo clients (Sharma Steels, Gupta Fabricators,
Patel Engineering Works). The phones belong to us, but no real customer data appears anywhere.

---

## Before the recording day

Do these once and check each one off. Scene-specific prep is listed under each scene.

### Accounts and numbers
- [ ] Three WhatsApp numbers verified as test recipients in the Meta app (the limit is 5):
  - **Sharma phone**: the client in scenes 2–4
  - **Gupta phone**: the client in scene 5
  - **Owner phone**: gets the buttons and the briefing. Set it as `OWNER_WA_NUMBER` on Render.
- [ ] Save the bot number on both client phones as **Recall Factory**. Save the contacts on the owner phone with demo names only.
- [ ] Recall can only send free-form messages and buttons to a number that messaged it in the last 24 hours. **The owner phone sends "hi" to the bot on recording day before scene 5.** The client phones are fine because they send voice notes first.

### Data (on recording day, because the seed dates are relative to today)
- [ ] Start from an empty Supabase DB so the order ids are 1–6 (bracket = #1, Gupta 2mm MS sheet = #3).
- [ ] Seed with the real test numbers:
  ```bash
  cd backend && uv run python -m scripts.seed --sharma-phone <sharma> --gupta-phone <gupta>
  ```
- [ ] Create Gupta's second MS sheet order so scene 5 is really ambiguous. From the **Gupta phone**, send this voice note:
  > "Gupta Fabricators se bol raha hoon. Naya order likh lijiye, teen mm MS sheet, chaalees piece, rate chaudah sau, Thursday tak."

  If the owner gets a "naya order ya #3 ka update?" question, tap **✅ Naya order**. Check that the dashboard now shows two Gupta MS sheet orders (2mm #3 and 3mm #7). The question in scene 5 should name both.
- [ ] Do a full rehearsal on a throwaway DB first. Reset and re-seed before the real take so the ids match this script.

### Backend and budget
- [ ] Render deploy is on the latest `main`. Open `/health` 2 minutes before every take, because a cold start takes about 1 minute.
- [ ] `WA_DAILY_SEND_CAP` leaves room. One full take sends about 5 messages (summary, buttons, tap reply, Gupta summary, briefing), and rehearsals count too.
- [ ] Gnani credits: every newly recorded voice note is a new Prisma call, and every briefing is a Timbre call. Plan on 3 takes per scene at most.
- [ ] Groq key works (send one test note). The Gemini fallback key is set.
- [ ] Eval has been run and `eval/results.md` exists (scene 7).

### Recording setup
- [ ] Mirror the phones to the Mac: iPhone Mirroring, or `scrcpy` for Android. Record the screen with OBS.
- [ ] **System audio is captured**, so the proof clip and the briefing are audible. Use OBS with BlackHole, or another loopback device. QuickTime alone does not record system audio.
- [ ] Dashboard open on the Vercel URL, browser zoom 125%, bookmarks bar hidden, notifications off (macOS Focus mode).
- [ ] Blur or crop the real phone numbers in the WhatsApp headers when editing.
- [ ] Phone clock visible in at least one shot of each phone. Real wait times are more convincing than jump cuts.

---

## Full cut (2:30)

| # | Scene | Time | Length |
|---|---|---|---|
| 1 | Problem | 0:00–0:15 | 15 s |
| 2 | Client sends a voice note | 0:15–0:35 | 20 s |
| 3 | Client gets a summary | 0:35–0:50 | 15 s |
| 4 | Dashboard and proof clip | 0:50–1:20 | 30 s |
| 5 | Unclear note goes to the owner | 1:20–1:50 | 30 s |
| 6 | Morning briefing | 1:50–2:10 | 20 s |
| 7 | Eval numbers | 2:10–2:25 | 15 s |
| 8 | Close | 2:25–2:30 | 5 s |

Speaking pace is about 2.5 words a second. The lines below fit their slots at that pace. Keep them short and let the screen do the talking.

### Scene 1. Problem (0:00–0:15)

**On screen:** A notebook with messy order notes, or a stock shot of a fabrication workshop. The title card **Recall** fades in at the end.

**Say:**
> "Chhoti factories mein saara business phone pe hota hai. Client order deta hai, quantity badhata hai, rate kam karwata hai, aur kuch likha nahi jaata. Phir delivery miss, billing galat, aur jhagda. Recall isko fix karta hai."

**Ready before recording:**
- [ ] Workshop B-roll or a photo of a messy order diary (no real names or numbers on it)
- [ ] Title card: "Recall: voice notes → live order book"

### Scene 2. Client sends a Hinglish voice note (0:15–0:35)

**On screen:** The Sharma phone (mirrored), in the WhatsApp chat with **Recall Factory**. Hold record and speak, release, and the voice note shows as sent. Cut to a split screen with the dashboard on the right showing the bracket row: **200 pcs, ₹45**.

**Voice note (Famous or a friend speaks it as Sharma ji, 8–10 s):**
> "Haan bhaiya, Sharma Steels se bol raha hoon. Wo do sau bracket wala order hai na, usko teen sau kar do. Aur rate bayalis rupaye laga dena, bulk order hai."

**Say (over the second half):**
> "Client wahi karta hai jo roz karta hai: WhatsApp pe ek voice note. Koi naya app nahi, koi form nahi."

**Ready before recording:**
- [ ] Sharma phone mirrored, chat with the bot open, and old test messages cleared from the chat
- [ ] The dashboard tab on the home page, with bracket #1 visible at 200 / ₹45
- [ ] The speaker has rehearsed the line 2–3 times. A quiet room is fine, but light background noise is good
- [ ] `/health` hit just before

### Scene 3. Client gets a summary (0:35–0:50)

**On screen:** The same Sharma phone. The reply arrives:
```
Namaste Sharma Steels ji, aapka voice note mil gaya.
✅ Order #1 (bracket) update: bracket, 300 pcs, ₹42 rate
```
Zoom in on the message. A small overlay shows the real wait time, for example "~20 s later". Measure it on the day and don't hide it.

**Say:**
> "Gnani ka Prisma Hinglish voice note ko text banata hai, LLM order nikalta hai, aur client ko turant confirmation milta hai: kya likha gaya, kaunsa order."

**Ready before recording:**
- [ ] Time the gap from send to reply in the rehearsal, so the overlay is honest
- [ ] If the reply says anything else (a pending line, the wrong order), stop, reset the DB, and retake. Don't edit the text.

### Scene 4. Dashboard shows the update with proof clip (0:50–1:20)

**On screen:**
1. Dashboard home. The Sharma bracket row now reads **300 pcs, ₹42** (auto refresh, no reload).
2. Click the row to open **Order #1**.
3. **Change history**: two cards, **quantity 200 → 300** and **rate ₹45 → ₹42**, each with "Proof clip 0:0x–0:0x of call".
4. Press play. The client's own voice says "...do sau bracket wala order... teen sau kar do... rate bayalis..." and nothing else plays.

**Say:**
> "Dashboard pe order khud update ho gaya: do sau se teen sau, rate paintaalees se bayalis. Aur har change ke saath proof hai. Ye suno, client ki apni awaaz, exact wahi hissa jahan usne bola. Ab koi jhagda nahi."

(Pause the narration while the clip plays, 4–6 s.)

**Ready before recording:**
- [ ] System audio capture tested with this exact clip (scene 3's note must already be processed)
- [ ] Play the clip once off camera to check the start/end. If it cuts mid-word, note it, but don't fake it
- [ ] Mouse cursor highlighting on (OBS or a cursor tool) so viewers see the clicks

### Scene 5. Unclear note goes to the owner as buttons (1:20–1:50)

**On screen:**
1. The Gupta phone. Gupta ji sends a voice note:
   > "Gupta ji bol raha hoon. Wo MS sheet wala order hai na, uski quantity do sau piece kar do. Rate wahi rakhna."
2. The Gupta phone gets this. Nothing is saved yet:
   ```
   Namaste Gupta Fabricators ji, aapka voice note mil gaya.
   ⏳ 1 baat owner se confirm karke batayenge.
   ```
3. Cut to the owner phone. The button message arrives:
   ```
   Gupta Fabricators: update (MS sheet, 200 pcs). Kaunse order ka hai? #3 MS sheet 100, #7 MS sheet 40
   "...MS sheet wala order hai na, uski quantity do sau piece kar do..."
   [Order #3]  [Order #7]  [❌ Nahi]
   ```
4. The owner taps **Order #3**. The reply: `✅ Order #3 update ho gaya: MS sheet, 200 pcs`.
5. Quick cut to the dashboard: Gupta's 2mm MS sheet is now 200, and the Pending page is empty.

**Say:**
> "Lekin Recall kabhi andaaza nahi lagata. Gupta ji ke do MS sheet orders hain, aur unhone bataya nahi kaunsa. To ye seedha owner ke paas jaata hai, do buttons ke saath. Owner ek tap karta hai, aur tabhi order update hota hai."

**Ready before recording:**
- [ ] Gupta's second MS sheet order (#7) exists (see "Before the recording day")
- [ ] The owner phone messaged the bot in the last 24 hours, or the buttons won't send
- [ ] Owner phone mirrored, or film it with a second camera for a real thumb tap
- [ ] Note the real button labels from the rehearsal. The ids may differ, so say what's on screen, not what's in this script
- [ ] The Pending page is open in a second tab for the quick cut

### Scene 6. Morning briefing voice note (1:50–2:10)

**On screen:** The owner phone. A voice note from Recall arrives. Play it with the waveform visible. Add captions of the spoken text.

Expected content (the order may differ), based on the seed plus scene 5:
> "Good morning. Aaj do deliveries hain. Gupta Fabricators ko do sau pieces 2mm MS sheet. Patel Engineering Works ko pachchees pieces 6 inch flange. Kal do deliveries hain. Sharma Steels ko teen sau kilo 40x40x5 angle. Gupta Fabricators ko chaalees pieces ISMC 75 channel."

Trim the playback to about 12 s in the edit if it runs long.

**Say (before it plays):**
> "Har subah owner ko Gnani Timbre ki awaaz mein briefing milti hai: aaj aur kal kya deliver karna hai. Dekho, Gupta ka order ab do sau hai, jo abhi tap kiya tha."

**Ready before recording:**
- [ ] Trigger it on camera, or just before the shot:
  ```bash
  curl -X POST https://<render-app>/briefing/send -H "Authorization: Bearer $CRON_SECRET"
  ```
- [ ] Captions written from the `text` field the endpoint returns
- [ ] Owner phone volume up, and system audio captured
- [ ] If Timbre fails, the endpoint sends text instead. Retake, don't use the text version for this scene

### Scene 7. Eval numbers (2:10–2:25)

**On screen:** One clean slide. The numbers come from `eval/results.md` (run on 9 Nov 2026, 16:35 IST). The 10 notes hold 12 order items, because two notes have two items each.

| | Clean | Noisy (8 kHz phone + factory noise) |
|---|---|---|
| Transcription WER | 12.1% | 11.8% |
| Extraction accuracy (item, qty, rate, date all right) | 10/12 | 10/12 |
| Matching accuracy (right order updated) | 9/12 | 11/12 |
| Sent to the owner instead of guessed | 4/12 | 2/12 |
| Voice note → order | ~4 s median | |

Footer: "10 synthetic Hinglish voice notes, voiced with Timbre, squeezed to 8 kHz with noise. No real customer data. Latency is Prisma + LLM, without WhatsApp delivery."

**Say:**
> "Humne dus synthetic Hinglish voice notes pe test kiya, clean aur noisy phone audio pe. Dono pe baarah mein se das items sahi nikle. Aur jab Recall sure nahi hota, wo guess nahi karta. Wo owner se poochta hai. Ek bhi item galat order mein save nahi hua."

Notes for the presenter:
- The "doesn't guess" line is backed by the eval. The ambiguous note (Gupta's two MS sheet orders) went to the owner in both variants. Every matching miss was a low-confidence item sent to the owner instead of saved (3 in the clean run, 1 in the noisy run). No item was saved to the wrong order.
- Don't say noise makes it better. Noisy matching scoring higher is chance on a 10-note set; numbers vary by about one item between runs.
- Say "around four seconds". The exact medians are 3.8 s clean and 4.2 s noisy, without the database and WhatsApp time, so on the video the reply takes longer. Scene 3's overlay shows the real wait.

**Ready before recording:**
- [x] Eval run, `eval/results.md` reviewed
- [ ] Slide made with large text that is readable on a phone screen

### Scene 8. Close (2:25–2:30)

**On screen:** The dashboard with a full order list, then the logo card: **Recall**. "Built on Gnani Prisma + Timbre". Team names.

**Say:**
> "Recall. Client bas bolta hai, order book khud banti hai."

**Ready before recording:**
- [ ] End card with the repo or demo link, and both names (Akshat Patil, Famous Raj Bhat)

---

## Short cut (60 s)

Same footage, tighter cuts, new voice-over. Record this narration separately after the full cut is edited, so it matches the trimmed shots.

| # | Scene | Time | On screen (from the full cut) | Say |
|---|---|---|---|---|
| 1 | Problem | 0:00–0:07 | Diary B-roll, title card | "Factory ka saara business phone pe, aur kuch likha nahi jaata." |
| 2 | Voice note | 0:07–0:17 | The Sharma voice note (keep about 6 s of the client's audio) | Let the client's voice play. No narration. |
| 3 | Summary | 0:17–0:22 | The summary message, zoomed | "Client ko turant confirmation." |
| 4 | Dashboard + proof | 0:22–0:36 | Row updates to 300 / ₹42, the change cards, the clip plays for 3 s | "Order khud update: teen sau, bayalis rupaye. Aur har change ke saath client ki apni awaaz ka proof." |
| 5 | Owner buttons | 0:36–0:46 | The button message, thumb taps Order #3 | "Confuse hua? To owner se poochta hai. Ek tap." |
| 6 | Briefing | 0:46–0:52 | Briefing voice note, about 4 s of audio with captions | "Har subah, aaj ki deliveries ki voice briefing." |
| 7 | Eval | 0:52–0:57 | The eval slide, extraction (10/12 noisy) and matching (11/12 noisy) highlighted | "Noisy phone audio pe bhi baarah mein se das sahi. Sure nahi, to owner se poochta hai." |
| 8 | Close | 0:57–1:00 | Logo card | "Recall. Bas bolo, order book ban jaati hai." |

Short cut rules:
- Burned-in captions on every line, because people watch with the sound off.
- Vertical 9:16 crop version for social posts: the phone screen fills the frame, and the dashboard goes picture-in-picture.

---

## On the day: order of shooting

Film in story order, because each scene changes the DB the next one shows.

1. Hit `/health`. The owner phone sends "hi" to the bot.
2. Scenes 2 → 3 → 4 (Sharma)
3. Scene 5 (Gupta → owner tap)
4. Scene 6 (briefing)
5. Scenes 1, 7, 8 any time (no live system)

If a take goes wrong in scenes 2–6: reset the DB, re-seed, and redo the Gupta prep note before retaking. Otherwise the ids and numbers on screen won't match.

Last check before upload: no real phone numbers visible, no `.env` or keys in any terminal shot, and every number in scene 7 matches `eval/results.md`. If the eval is re-run, update scene 7 from the new file.
