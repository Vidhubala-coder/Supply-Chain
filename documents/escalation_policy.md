# Incident Escalation Policy

## Section 1: Ambiguous Entity Resolution
If a disruption notice cannot be matched with high confidence to a single supplier or shipment (AMBIGUOUS state), automatic pipeline processing must halt and escalate to human operators for manual entity selection.

## Section 2: Critical Contradictions
When a disruption notice conflicts with database records regarding supplier, product, or quantity (CRITICAL CONTRADICTION), pipeline execution must pause and trigger immediate compliance escalation.

## Section 3: Escalation Audit Trail
All escalated incidents must record timestamped audit log entries with operator notes and resolution state.
