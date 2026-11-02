# Trino Query Queueing

Services: trino
Keywords: trino query queued queueing resource group coordinator memory cluster overloaded worker

## Symptoms
- Queries sit in QUEUED state for minutes.
- Users report slow dashboards and timeouts.
- Coordinator or worker memory is near its limit.

## Diagnosis
1. Check the queued and running query counts per resource group.
2. Identify the heaviest queries by memory and CPU in the query UI.
3. Check worker count and node health; look for workers that dropped out.
4. Check whether one team or user dominates the resource group.

## Mitigation
1. Kill runaway queries that exceed their memory or time budget.
2. Adjust resource group limits so one workload cannot starve others.
3. Add or restore worker nodes if capacity dropped.
4. Ask the owning team to add filters, partition pruning, or LIMIT clauses.

## Escalation
Escalate to the Data Platform on-call if queued queries exceed 100 for more than 10 minutes, or if the coordinator becomes unresponsive.
