from app.scheduler.__main__ import build_scheduler


def test_scheduler_has_one_p0_heartbeat_job() -> None:
    scheduler = build_scheduler()

    jobs = scheduler.get_jobs()
    assert [job.id for job in jobs] == ["p0-heartbeat"]
    assert jobs[0].max_instances == 1
    assert jobs[0].coalesce is True
