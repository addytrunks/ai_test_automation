import asyncio
import time
import urllib.request
import uuid

from sqlalchemy import select

from app.auth.service import hash_password
from app.db import get_sessionmaker
from app.generator.service import generate_test_suite_task
from app.models import Project, Test, TestSuite, User
from app.specs.service import ingest_spec


async def run_scenario():
    print("Starting VAmPI Metrics Scenario...")
    session_factory = get_sessionmaker()
    
    # 1. Setup Data
    async with session_factory() as db:
        # Create user
        user = User(
            email=f"test_{uuid.uuid4()}@example.com", 
            password_hash=hash_password("password"),
            name="Metrics Tester"
        )
        db.add(user)
        await db.flush()
        
        # Create project
        project = Project(
            user_id=user.id,
            name="VAmPI Metrics Run",
            target_base_url="http://localhost:5001"
        )
        db.add(project)
        await db.commit()
        await db.refresh(user)
        await db.refresh(project)

    # 2. Upload Spec & Parse
    print("Fetching VAmPI spec...")
    start_time = time.time()
    try:
        req = urllib.request.urlopen('http://localhost:5001/openapi.json')  # noqa: ASYNC210
        spec_content = req.read()
    except Exception as e:
        print(f"Failed to fetch VAmPI spec: {e}")
        return

    async with session_factory() as db:
        spec, endpoints = await ingest_spec(db, user.id, project.id, spec_content)
        
        suite = TestSuite(
            project_id=project.id,
            spec_id=spec.id,
            name="Metrics Suite"
        )
        db.add(suite)
        await db.flush()
        
        # Find auth endpoint for VAmPI
        auth_endpoint_id = None
        register_endpoint_id = None
        for ep in endpoints:
            if ep.method.lower() == 'post' and 'login' in ep.path.lower():
                auth_endpoint_id = ep.id
            if ep.method.lower() == 'post' and 'users/v1' in ep.path.lower() and 'register' in ep.summary.lower() if ep.summary else False:
                # Actually VAmPI register is /users/v1
                register_endpoint_id = ep.id
        
        if not register_endpoint_id:
            for ep in endpoints:
                if ep.method.lower() == 'post' and 'users/v1/register' in ep.path.lower() or ep.method.lower() == 'post' and 'users/v1' in ep.path.lower():
                    register_endpoint_id = ep.id

        await db.commit()
        await db.refresh(suite)
        
        endpoint_ids = [ep.id for ep in endpoints]
        
    spec_upload_time = time.time() - start_time
    print(f"Spec uploaded and parsed in {spec_upload_time:.2f}s")
    
    # 3. Baseline Generation (Iteration 0)
    print("Generating baseline tests (Iteration 0)...")
    baseline_start = time.time()
    scenarios = ["positive", "negative", "boundary", "bola", "auth_bypass", "injection", "mass_assignment"]
    
    # Run the background task directly inline to time it
    await generate_test_suite_task(
        suite_id=suite.id, 
        endpoint_ids=endpoint_ids, 
        scenarios=scenarios, 
        auth_endpoint_id=auth_endpoint_id, 
        register_endpoint_id=register_endpoint_id
    )
    
    baseline_time = time.time() - baseline_start
    print(f"Baseline tests generated in {baseline_time:.2f}s")
    
    # Fetch Final Metrics
    async with session_factory() as db:
        result = await db.execute(select(Test).where(Test.test_suite_id == suite.id))
        tests = list(result.scalars().all())
        
        iteration_counts = {}
        for t in tests:
            iteration_counts[t.generation_depth] = iteration_counts.get(t.generation_depth, 0) + 1
    
    total_time = time.time() - start_time
    
    # Write to metrics_log.txt
    metrics = f"""
Date: {time.strftime('%Y-%m-%d %H:%M:%S')}
Spec: VAmPI (from http://localhost:5001/openapi.json)
Iterations run: 0 (Baseline only)
Tests generated (per iteration): {iteration_counts}
Generation time (seconds):
- Spec upload & parse: {spec_upload_time:.2f}s
- Baseline Generation (Iter 0): {baseline_time:.2f}s
- Time from spec upload to first batch ready: {spec_upload_time + baseline_time:.2f}s
Total Time: {total_time:.2f}s
Notes: Automated metrics extraction run (Generation Time ONLY).
--------------------------------------------------
"""
    
    with open("../metrics_log.txt", "a") as f:  # noqa: ASYNC230
        f.write(metrics)
    
    print("Metrics appended to metrics_log.txt")

if __name__ == "__main__":
    asyncio.run(run_scenario())
