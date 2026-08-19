---
title: <Computation Name>
type: attested-computation
description: <one-line summary used by index.md, search snippets, and previews>
tags: [computation, <domain tags>]
runtime: <how to run, e.g. python3, deno, node>
parameters:
  - name: <param>
    type: <type, e.g. int, str, list[float]>
    description: <what this parameter represents>
computation: <bundle-relative path to the computation file, e.g. scripts/compute.py>
executor:
  resource: <how to invoke, e.g. scripts/run.sh>
  receipt: <where the executor writes its receipt, e.g. out/receipt.json>
attester:
  resource: <deterministic check command, e.g. scripts/verify.py>
generated:
  by: <actor convention>
  at: <YYYY-MM-DD>
status: draft
---

# <Computation Name>

<1-2 sentence description of what this computation does and what it attests to.>

## Parameters

| Name | Type | Description |
|------|------|-------------|
| <param> | <type> | <what this parameter represents> |

## How to Run

```
<executor invocation>
```

The executor writes a receipt to `<receipt path>` describing the inputs, environment, and outputs.

## Attestation

A separate deterministic check (`attester.resource`) re-runs the computation on the receipt inputs and compares against the receipt's claimed output.

## See Also

- [related-concept](../concepts/related-concept.md)