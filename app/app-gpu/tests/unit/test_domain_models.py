from appgpu.domain import MiningJob, PipelineStage


def test_mining_job_add_stage():
    job = MiningJob(job_id="1", payload={"x": 1.0}, priority="red", deadline_ms=120)
    stage = PipelineStage(name="stage", duration_budget_ms=10, max_concurrency=2)

    job.add_stage(stage)

    assert job.stages[0].name == "stage"


def test_deadline_kept():
    job = MiningJob(job_id="1", payload={}, priority="green", deadline_ms=200)
    assert job.deadline_ms == 200
