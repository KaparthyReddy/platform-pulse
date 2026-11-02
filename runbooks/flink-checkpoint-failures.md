# Flink Checkpoint Failures

Services: flink
Keywords: flink checkpoint failure timeout backpressure state backend savepoint restart lag

## Symptoms
- Checkpoint failure or timeout alerts fire repeatedly.
- Job restarts in a loop and consumer lag grows.
- Checkpoint duration trends upward over days.

## Diagnosis
1. Open the Flink UI checkpoint tab; find the operator with the longest alignment time.
2. Check backpressure on the slow operator and its downstream sink.
3. Check state size growth; unbounded state slows every checkpoint.
4. Check the storage backend for throttling or errors.

## Mitigation
1. Fix the backpressured sink or downstream dependency first.
2. Increase checkpoint timeout temporarily and enable unaligned checkpoints.
3. Add state TTL or reduce key cardinality to bound state size.
4. Take a savepoint, then restart with higher parallelism on the bottleneck operator.

## Escalation
Escalate to the Data Platform on-call if checkpoints fail for more than 30 minutes, or if the job cannot restore from its last good checkpoint.
