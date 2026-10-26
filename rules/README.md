# Rule tables

All agronomy values live here, not in code (spec rule 3, NFR7). The engine in `engine/` loads these files; changing a value here changes the advice without a code change.

Every entry is a rule with:

| Field | Meaning |
|---|---|
| `id` | Stable ID, recorded on every piece of advice it fires in |
| `status` | `draft`, `agronomist_input` or `verified` |
| `source_type` | `published`, `expert_opinion`, `derived` or `proposed` |
| `source_doc` | Name of the published document, or `null` |
| `reviewer_alias` | Alias only, never a name (`AGR-1` is the first, anonymous reviewer) |
| `ref` | Questionnaire item or spec section the value comes from |
| `ph_method` | For pH-dependent rules: `water`, `cacl2` or `unconfirmed` |
| `data` | The values |

A value of `OPEN` means nobody has supplied it; `CONFLICT` means two answers disagree (spec section 7). The engine never invents a replacement: anything that depends on one returns "lab test recommended".

`AGR-1` will not confirm these tables, so a rule supported only by `AGR-1` expert opinion cannot be `verified`. `python -m engine.validate` checks this and lists every `OPEN` and `CONFLICT` value.
