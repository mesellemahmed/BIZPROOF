# Matched baseline comparison

| Method | Budget | Detected | Rate | Interpretation |
|---|---:|---:|---:|---|
| BIZPROOF | frozen-proof | 14/14 | 100.0% | formal source-equivalence plus mutant disproof |
| Hypothesis | 100 | 14/14 | 100.0% | counterexample search; absence is inconclusive — 1.976s |
| Hypothesis | 1000 | 14/14 | 100.0% | counterexample search; absence is inconclusive — 0.799s |
| Hypothesis | 10000 | 14/14 | 100.0% | counterexample search; absence is inconclusive — 0.813s |
| CrossHair | 0.5 | 5/14 | 35.7% | symbolic assertion search; absence is inconclusive — 15.552s |
| CrossHair | 2.0 | 7/14 | 50.0% | symbolic assertion search; absence is inconclusive — 17.139s |
