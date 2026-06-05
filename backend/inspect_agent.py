import asyncio
from app.db import get_sessionmaker
from app.models import Run, Test, TestResult, CoverageGap, AIAnalysis
from sqlalchemy import select

async def inspect():
    suite_id = '5d002067-ae98-4c16-b7d2-d0699c08cbf9'
    db_maker = get_sessionmaker()
    
    async with db_maker() as db:
        # 1. RUNS
        res = await db.execute(select(Run).where(Run.test_suite_id == suite_id).order_by(Run.loop_iteration))
        runs = list(res.scalars().all())
        print(f"=== RUNS ({len(runs)}) ===")
        for r in runs:
            print(f"Run {r.id}: Iteration {r.loop_iteration}, Status: {r.status}")
            if r.status in ['running', 'analyzing', 'pending']:
                print(f"  -> FIXING stuck run {r.id} to 'error'")
                r.status = 'error'
                
        # 2. COVERAGE GAPS
        res = await db.execute(select(CoverageGap).where(CoverageGap.test_suite_id == suite_id).order_by(CoverageGap.created_at))
        gaps = list(res.scalars().all())
        print(f"\n=== COVERAGE GAPS ({len(gaps)}) ===")
        for g in gaps:
            print(f"[{g.severity}] {g.scenario_description}")
            
        # 3. AI FAILURES ANALYSES
        if runs:
            # Check for analyses in iteration 0
            res = await db.execute(select(TestResult).where(TestResult.run_id == runs[0].id))
            results_iter0 = {r.id: r for r in res.scalars().all()}
            res = await db.execute(select(AIAnalysis).where(AIAnalysis.test_result_id.in_(list(results_iter0.keys()))))
            analyses = list(res.scalars().all())
            print(f"\n=== AI FAILURES ANALYSES (Iteration 0) ({len(analyses)}) ===")
            for a in analyses[:5]: # Show max 5
                print(f"Likely Cause: {a.likely_cause[:100]}...")
                
        # 4. AGENT GENERATED TESTS
        res = await db.execute(select(Test).where(Test.test_suite_id == suite_id, Test.generation_depth > 0).order_by(Test.generation_depth))
        new_tests = list(res.scalars().all())
        print(f"\n=== AGENT GENERATED TESTS ({len(new_tests)}) ===")
        for t in new_tests:
            print(f"\n[{t.generation_depth}] {t.name}")
            print(f"Endpoint: {t.method} {t.path}")
            print(f"Path Params: {t.path_params}")
            print(f"Body: {t.body}")
            print(f"Headers: {t.headers}")
            print(f"Extract: {t.extract}")
            print(f"Static: {t.static_context}")
            
            # Show the results for this new test if it was run
            res_tr = await db.execute(select(TestResult).where(TestResult.test_id == t.id))
            test_results = list(res_tr.scalars().all())
            for tr in test_results:
                print(f"  => Run {tr.run_id}: Status={tr.status}, ResStatus={tr.response_status}")
                if tr.error_message:
                    print(f"     Error: {tr.error_message}")
                
        await db.commit()

if __name__ == '__main__':
    asyncio.run(inspect())
