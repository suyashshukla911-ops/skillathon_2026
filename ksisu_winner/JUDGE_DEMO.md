# 3-minute judge demonstration — final flow

## 0. Start

Run `run.bat`. In the GUI, `Run 3-Min Judge Demo` performs the baseline → real-evidence comparison automatically; the step-by-step buttons remain available for manual demonstration.

The GUI starts in **proxy baseline** mode and does not permit manual invention of supply numbers.

## 1. Baseline — show the discipline

Click **Run Proxy Baseline**.

Open **2. Gap Results**.

Say:

> “The model produces an analytical alignment interval, but policy status remains NEEDS DATA because district ITI supply is still a proxy.”

This immediately avoids the earlier failure where every district was presented as a proven gap.

## 2. Show where KSISU should collect data first

Open **3. District Priority**.

Point to:

- SCI
- VOI
- Data priority
- evidence score

Say:

> “We are not ranking districts by size alone. We rank the value of resolving their uncertainty, weighted by the stakes.”

## 3. Load real district evidence

Click **Load Official NCVT Sample** for the bundled demonstration, or **Load Real District Supply CSV** for the full current district x trade extract.

The bundled file is an official NCVT MIS indexed subset containing real Tumakuru and Kalaburagi rows, but it is explicitly labelled partial and historical.

## 4. Re-run

Click **Run With Loaded Supply**.

Open **2. Gap Results**.

Show that the affected cells now say `partial-observed-floor` rather than `district-proxy`.

They remain `NEEDS DATA` because coverage is incomplete. The interval change is not presented as a certainty gain: the observed seats are treated as a floor and the unobserved remainder stays uncertain.

## 5. Prove the uncertainty change

Open **5. Validation & Linkage**.

Show the partial-evidence update table: before width, after width, width change, and whether the interval widened or narrowed.

Say:

> “This experiment shows how the same model responds to better evidence. With a partial file the interval can widen; a complete district extract is the condition for a genuine uncertainty reduction.”

For the bundled partial NCVT evidence, describe the result as a **lower-bound evidence update**. In this run the affected intervals widen because the observed subset is much smaller than the prior proxy; that is a diagnostic that the proxy is weak, not a reason to claim certainty. A full district extract is required before a strong district policy call.

## 6. Sensitivity

Open **4. Sensitivity**.

Say:

> “We test rank stability across the shared Monte Carlo draws. This shows whether a data-collection priority is stable under common uncertainty, rather than simply repeating the chosen input ranges.”

## 7. Validation

Open **5. Validation & Linkage**.

Show:

- seeded typo recovery;
- unseen aliases sent to review;
- duplicates flagged;
- no unmatched rows dropped;
- provenance and source file registry.

## Closing line

> “The product is not the dashboard. The product is a reproducible evidence pipeline that tells KSISU what it can infer today, what it cannot infer, and which district evidence to collect first.”

## Final competition upgrade

Before submission, replace the bundled partial file with the **complete current NCVT MIS/DGT/Karnataka district×trade seat extract** and re-run. Do not type or fabricate missing seats.
