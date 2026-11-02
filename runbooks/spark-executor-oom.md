# Spark Executor Out-Of-Memory

Services: spark
Keywords: spark executor oom memory container killed shuffle spill gc overhead

## Symptoms
- Jobs fail with ExecutorLostFailure or "Container killed by YARN/Kubernetes for exceeding memory limits".
- Stages retry repeatedly, then the job aborts.
- Executor GC time exceeds 20% of task time.

## Diagnosis
1. Open the Spark UI and find the failing stage; check task skew in the stage summary.
2. Compare max task memory against the median. A large gap means data skew.
3. Check shuffle spill (memory and disk). Heavy spill means partitions are too large.
4. Look for collect(), large broadcast joins, or wide aggregations in the job.

## Mitigation
1. Increase spark.executor.memoryOverhead before raising executor memory.
2. Raise spark.sql.shuffle.partitions to shrink partition size.
3. Enable adaptive query execution: spark.sql.adaptive.enabled=true.
4. Salt skewed join keys or enable skew join handling.
5. Replace broadcast joins with sort-merge joins when the broadcast side is large.

## Escalation
Escalate to the Data Platform on-call if more than three jobs from different teams fail within an hour, which points to a cluster-wide memory or node issue.
