# Airflow Scheduler Lag

Services: airflow
Keywords: airflow scheduler lag delayed dag queued tasks heartbeat pool slots parsing

## Symptoms
- Tasks stay in queued or scheduled state far longer than expected.
- Scheduler heartbeat age exceeds 30 seconds.
- DAGs miss their expected start times.

## Diagnosis
1. Check scheduler heartbeat and the scheduler logs for errors or restarts.
2. Check DAG file parse time; slow parsing delays scheduling for every DAG.
3. Check pool slot usage and parallelism limits for starvation.
4. Check metadata database latency and connection count.

## Mitigation
1. Restart an unhealthy scheduler and confirm the heartbeat recovers.
2. Reduce top-level code in DAG files and increase min_file_process_interval.
3. Raise pool slots or parallelism if workers are idle while tasks queue.
4. Scale database resources or clean old task instances and logs.

## Escalation
Escalate to the Data Platform on-call if the scheduler heartbeat stays stale after a restart, or if metadata database latency stays elevated for more than 15 minutes.
