# Reading a bill

How a photo or PDF of a TGSPDCL or TGNPDCL bill becomes numbers we trust, and when we ask for a clearer photo
instead. Domestic, non-domestic (LT-II) and solar net-metered bills go through the same path.

The rule that decides everything: **a reading is trusted only when its numbers check out against each other.** The
model's own confidence is never enough, and no number is ever worked out to fill a gap. A wrong reading that we trust
is the one outcome that must not happen; asking for a retake is the safe fallback.

## The path

1. **Open and straighten** (`services/vision.py`). PDFs are rendered page by page, HEIC opens, tiny WhatsApp photos
   are enlarged, and a photo tilted 3 degrees or more is turned straight (`skew_angle`), because on a tilted slip a
   value drifts onto the row above or below its label. Tall slips are sent as overlapping crops.
2. **First look.** A cheap pass decides whether it is an electricity bill, a meter photo or something else. Only a
   bill or a meter is read in detail.
3. **Careful read.** The model returns the printed values only: readings with their meter status, units, solar
   import, export, billed units and the export register's own readings, MF, every charge row, totals, dates.
4. **One form** (`domain/bill_normalise.py`). "Rs 1,234.50", "545.00 CR", "07/09/26", "Sts 1", "TSSPDCL" and a power
   factor of 99 are put in one form. A value that still does not fit is dropped and listed as unreadable, so one bad
   cell never loses the rest of the bill. The printed category decides domestic or not.
5. **Checks** (`domain/capture.py`). The ones that block trust:

   | Check | What it catches |
   | --- | --- |
   | Present minus previous reading, times MF, equals units (meter rollover allowed) | A misread reading or units |
   | Export register readings equal the units exported (solar) | A misread export figure |
   | Import minus export equals billed units (solar) | A misread import, export or billed figure |
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

## Measuring it

`python -m app.tools.eval_bills <out_dir>` degrades the two real scans in `tests/real_bills` the ways phone photos
fail (blur, motion, tilt, glare, darkness, WhatsApp compression, a cut-off bottom), reads them live and scores each:
correct, retake, or TRUSTED_BUT_WRONG. It makes about two vision calls per case.

| Run (22 bill photos, 2 non-bills) | Correct | Retake | Trusted but wrong |
| --- | --- | --- | --- |
| Before this round | 16 | 6 | 0 |
| After | 17 | 5 | 0 |

Read correctly now that were retakes: the tilted March slip and the heavily blurred October slip. The remaining
retakes are right to be retakes: two photos have the bill amount cut off, two are blurred past reading, and one had
the units and a reading misread together, which the energy check caught.

There is no real solar photo in the test set yet. Solar bills are covered by unit tests on the September 2026
commercial bill fixture; add a scan of a solar bill to `tests/real_bills` and its expected values to `TRUTH` in the
eval to measure them live.
