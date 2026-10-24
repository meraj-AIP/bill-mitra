# Reading a bill

How a photo or PDF of a TGSPDCL or TGNPDCL bill becomes numbers we trust, and when we ask for a clearer photo
instead. Domestic, non-domestic (LT-II) and solar net-metered bills go through the same path.

The rule that decides everything: **a reading is trusted only when its numbers check out against each other.** The
model's own confidence is never enough, and no number is ever worked out to fill a gap. A wrong reading that we trust
is the one outcome that must not happen; asking for a retake is the safe fallback.

## The path

1. **Open, crop and straighten** (`services/vision.py`). PDFs are rendered page by page, HEIC opens, a slip that fills
   only part of the photo (on a bed or a table) is cropped to the paper (`paper_box`), a stamp or pen mark over the
   name does not split it, tiny WhatsApp photos are enlarged, and a photo tilted 3 degrees or more is turned straight (`skew_angle`), because on a tilted slip a
   value drifts onto the row above or below its label. Tall slips are sent as overlapping crops.
2. **First look.** A cheap pass decides whether it is an electricity bill, a meter photo or something else. Only a
   bill or a meter is read in detail.
3. **Careful read.** The model returns the printed values only: readings with their meter status, units, solar
   import, export and the export register's own readings, banked ("CF") units brought in and carried on, MF, every
   charge row, totals, dates. Each solar figure is copied under its printed label ("Units:", "Import:"); the code, not
   the model, decides that Import is the units drawn and Units the units billed, because the model asked to swap them
   itself did so unreliably. An export register read backwards is put in counting order unless it rolled over.
4. **One form** (`domain/bill_normalise.py`). "Rs 1,234.50", "545.00 CR", "07/09/26", "Sts 1", "TSSPDCL" and a power
   factor of 99 are put in one form. A value that still does not fit is dropped and listed as unreadable, so one bad
   cell never loses the rest of the bill. The printed category decides domestic or not.
5. **Checks** (`domain/capture.py`). The ones that block trust:

   | Check | What it catches |
   | --- | --- |
   | Present minus previous reading, times MF, equals units (meter rollover allowed) | A misread reading or units |
   | Export register readings equal the units exported (solar) | A misread export figure |
   | Import minus export minus units banked in equals billed units; any surplus is carried on (solar) | A misread import, export, billed or banked figure |
   | Units agree with the energy charge | Units and a reading misread the same way, so they still agree with each other |
   | Charges add up to the bill amount | A charge read from the wrong row |
   | Bill amount plus arrears equals total due | A misread total or arrears |

   On a solar bill whose net units add up, a misread meter reading alone does not block. The energy check only says
   "misread" when the printed energy charge fits a different unit count exactly; a charge that fits none is a pricing
   question for the audit, not a misread.
6. **Second read** (`domain/second_read.py`), only when the first fails a check or was unsure of units, energy, the
   bill amount or the total. It gets a sharpened copy, the name of the failed check and the charge rows that look
   wrong, never the expected numbers. The second read is used if it passes on its own (after doubt, only where both
   reads agree). If neither passes, the two reads are reconciled: every mix of the figures they disagree on is
   tried, and the result stands only when exactly one mix passes every check. A figure that only one read produced is
   never trusted, because a reader asked to look again may supply a value that is not printed.
7. **Otherwise** the consumer is asked for a clearer photo, with what we could and could not read.

### Reading twice

Every bill is read twice at once (`vision._read_twice`): the photo and a sharpened copy. Two views rarely share a
misread, and on one real bill a set of misread figures still added up, which no sum can catch. Where the two reads
disagree on a key figure (units, solar import, export, billed and banked units, any reading, any charge row, bill
amount, arrears, total, bill and due dates, load), a third read is told only which figures to look at and the value
two of three reads agree on stands (`second_read.vote`). A figure with no majority is cleared and marked unreadable
(`second_read.mark_undecided`): a units or money figure makes the bill untrusted, a date is shown as unclear. The two
reads run in parallel, so the time is about one read. `READ_TWICE=false` turns it off.

### Every printed line

Alongside the reads, one more request copies every printed line as label and value (`vision.transcribe`), so a
consumer can ask about anything on the bill. The consumer's name, address, mobile and email are left out by the
prompt and again by the code, including any fragment in the "Consumer Details" block. Lines for figures the checks
cover (readings, import, export, units, charges, amounts) are left out too: those questions are answered from the
checked figures, so a misread copy is never quoted. A question outside the fixed topics goes to the model, which may
only pick line numbers (`llm.pick_lines`); the reply quotes the lines as printed. A named term ("what is MD") whose
field the reader left empty quotes its printed line. Nothing checks these free lines, so on a poor photo a minor line
may be garbled; they never feed an amount. `READ_PRINTED_LINES=false` turns it off.

## Measuring it

`python -m app.tools.eval_bills <out_dir>` degrades the two real scans in `tests/real_bills` the ways phone photos
fail (blur, motion, tilt, glare, darkness, WhatsApp compression, a cut-off bottom), reads them live and scores each:
correct, retake, or TRUSTED_BUT_WRONG. It makes about two vision calls per case.

| Run (22 bill photos, 2 non-bills) | Correct | Retake | Trusted but wrong |
| --- | --- | --- | --- |
| Before this round | 16 | 6 | 0 |
| After | 17 | 5 | 0 |
| Read twice, paper crop, solar rules (Oct 2026) | 18 | 4 | 0 |

Read correctly now that were retakes: the tilted March slip and the heavily blurred October slip. The remaining
retakes are right to be retakes: two photos have the bill amount cut off, two are blurred past reading, and one had
the units and a reading misread together, which the energy check caught.

Solar is covered by the September 2026 commercial fixture and by two real domestic slips from October 2026
(`SOLAR_DOM_OCT_2026`, which exported more than it drew and carried 10 units on, and `SOLAR_DOM_AUG_2026`). On both,
duty is charged on the units imported, domestic as well as commercial, and the engine now does the same. A reading
that still fails its register check on a solar bill whose net units agree is dropped and marked unreadable rather than
shown. The photos themselves are not in the repo because they show the consumer's service number; add a scan of a solar bill to `tests/real_bills` and its expected values to `TRUTH` in the
eval to measure them live.
