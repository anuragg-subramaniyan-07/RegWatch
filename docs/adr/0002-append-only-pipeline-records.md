# ADR 0002: One record per completed pipeline stage, not one evolving row

## Status
Accepted

## Context
As a single notification passes through the pipeline , we want to decide if we want to maintain a single row for a notification and have all the different layers write onto that single row , or have each layer maintain its own separate record for each notification and only writes to its own record when it has successfully completed 

## Options Considered
Option - A : here we have one singular evolving row as a notification passes through all the layers , drawback here is that an empty field is ambiguous — we can't tell whether a stage simply hasn't run yet, or whether it ran and failed before writing its result, since both cases look identical (an empty field) 

Option - B : Each layer maintains its own record and only writes when that layer has successfully finished its work related to that notification and at the end , each completed layer gets stapled together 

## Decision
Option B 

## Consequences
The main consequence of choosing option B is that each layer/stage will maintain its own set of records , hence inorder to get the complete information about one single notification we would have to perform a join to obtain it unlike option A where its all stored together under a singular row 

Option B does not fully solve the ambiguity problem either — it guarantees that a stage's record is either complete or does not exist at all, so we never mistake broken/partial data for real output. But it still cannot tell us *why* a stage's record is missing: "hasn't started yet" and "started and failed" both simply look like "no record exists." Telling those apart is a separate, still-open problem, likely solved later with a job queue or run log rather than by this decision.
