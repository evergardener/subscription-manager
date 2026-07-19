from app.scheduler.__main__ import build_scheduler


def test_scheduler_has_bounded_heartbeat_and_reminder_jobs() -> None:
    scheduler = build_scheduler()

    jobs = scheduler.get_jobs()
    assert {job.id for job in jobs} == {"p0-heartbeat", "event-maintenance"}
    assert all(job.max_instances == 1 for job in jobs)
    assert all(job.coalesce is True for job in jobs)
