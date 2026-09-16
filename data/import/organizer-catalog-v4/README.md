# Organizer catalog v4 import bundle

This directory is the committed, text-only derived bundle for the explicit
catalog importer. It is not read by backend startup and it contains no original
PDF, XLSX, DOCX, or organizer CSV binaries.

Images from the restricted 91-page visual catalog are handled separately by
`python -m catalog_media`: the source PDF and extracted bytes remain local,
while PostgreSQL stores append-only checksums, dimensions, source page/slot and
the exact relation to each of the 223 catalog positions.

`manifest.json` is the authority for file hashes, byte sizes, record counts,
source-artifact metadata, and the versioned RUB/VAT product decision. The
importer verifies every entry before creating an `ImportRun`.

Import order:

1. `BASE` validates/imports 187 products, 223 source rows, 223 applicability
   rows, 223 price offers, 3635 base evidence rows, and 65 base spec facts.
2. `ENRICHMENT` validates/imports 140 overlay observations and 156 external
   evidence rows. It never updates organizer observations.

Only safe resolved statuses can enter `matching_spec_facts`. `CONFLICT`,
`AMBIGUOUS_MODEL_MATCH`, `NOT_FOUND`, and `UNKNOWN` remain observations.

The v4 price currency is RUB by a versioned product decision, not by inference
from the source CSV. VAT is marked `ORGANIZER_ASSUMPTION_INCLUDED`, with
`vat_rate = null`. Delivery, commissioning/start-up, and deep IT integration
remain excluded costs.

Rebuild from the ignored maintainer staging area:

```bash
python scripts/build_catalog_bundle.py
python scripts/build_catalog_bundle.py --check
```
