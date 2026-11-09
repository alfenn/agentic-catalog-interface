---
datetime: 2026-11-08-18-08
---

# human feedback to implement

do not use the language "smoke" anywhere in the project. "smoke test" is very jargon-y and reads like AI.

there should be a few citations to test run results in the "what did not work and pivots" and "results" sections as we want to update those sections to be grounded in the evidence and traces walking through what we expect and didn't expect. 

## writeup 

remove all cost data from the report. 

for now, do not include comparison against generic workflow. just include comparison against generic coding agent like pi and codex, as those are open sourced and this can serve as the "one significant result to report"

it's not clear how evaluation for each of these cases works in the writeup. it's should be explained more clearly. if evaluation method is reused, explain it step by step once. this is important enough to spend word count on in the report, as what we want to highlight is basically some initial results that our intervention works. 

### Problem statement

- this should not be limtied to dbt-backed lackhouse. it should be about lakehouses in general.


### what did not work and pivots

the way you should explain each of these points is by talking about what the agent did, whether the answer was right, and what i changed about the agent as a result.

### results

the metrics that are being reported, and the test cases, are not clear. it's also not clear what the charts show. it would be worth it in the writeup to go in-depth into 1-2 exemplary test cases to walk through how the evaluation worked from a qualitative analysis perspective (highlighting what the agent did, what you expected it to do, how it could have done better), and then explaining how these observations were reflected in the scoring.
