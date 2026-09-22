# Formula executability audit v3

Audit covers exactly 187 models and 223 positions. It validates dependency
origins, evidence, units and domains without executing formulas, reading Robot
costs, changing runtime activation or changing pool membership.

| Status | Models | Positions |
|---|---:|---:|
| CATALOG_EXECUTABLE | 21 | 24 |
| MISSING_SAFE_FACT | 19 | 19 |
| INVALID_FACT | 0 | 0 |
| UNKNOWN_IDENTITY | 0 | 0 |
| UNSUPPORTED_PROFILE | 143 | 176 |
| NOT_EQUIPMENT | 4 | 4 |

The catalog-executable identity set remains exactly 21 models / 24 positions;
the committed pool diff has no additions or removals. BAS is absent. A catalog
label is not run executability: every run must still provide normalized C03
scenario inputs and an acceptable C05 constraint report.
