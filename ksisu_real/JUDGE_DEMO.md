# 3-minute judge demonstration

## Before the demo

Have one real NCVT MIS/DGT/Karnataka district-trade CSV ready with columns:

`district,nco_group_2digit,seats`

or:

`district,trade,seats`

Prefer two pilot districts, for example Tumakuru and Kalaburagi.

## 1. Baseline

Launch `run.bat`.

Click **Run Analysis**.

Say:

> "This is the public-data baseline. The model does not pretend the district data is complete. It keeps the proxy visible."

Open **Gap Results**. The mathematical interval may be below 1 in some rows, but the **policy decision stays NEEDS DATA** because district supply is still proxy-based.

## 2. Show the data-onboarding priority

Open **District Priority**.

Say:

> "Instead of giving government a false red-green dashboard, we rank where better district data has the largest decision value."

Show SCI, VOI and confidence.

## 3. Replace the proxy with actual district ITI data

Click **Load Actual District Supply** or **Manual Supply Entry**.

Load the real downloaded values for Tumakuru / Kalaburagi.

Click **Run Analysis** again.

Rows switch from `district-proxy` to `district-actual`.

## 4. Prove that the interval changes

Open **Validation & Linkage**.

The GUI compares the previous proxy interval with the new actual-supply interval and reports how much narrower it became.

Say:

> "The uncertainty is not decorative. When KSISU acquires the missing district data, the interval shrinks."

## 5. Show sensitivity

Open **Sensitivity**.

Say:

> "We also know which assumption is driving the answer, so KSISU knows what to validate next."

## 6. Finish

Open **Validation & Linkage** and show the corruption test.

Final line:

> "The product is not the dashboard. It is a reproducible evidence pipeline that tells KSISU what it can infer today, what it cannot infer, and which district data to collect first."
