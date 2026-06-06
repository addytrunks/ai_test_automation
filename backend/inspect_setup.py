import asyncio

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import CoverageGap, Run, Test


async def inspect():
    suite_id = '510af5ed-1090-456a-939d-84af0c13cee6'
    db_maker = get_sessionmaker()
    
    async with db_maker() as db:
        res = await db.execute(select(Run).where(Run.test_suite_id == suite_id).order_by(Run.loop_iteration))
        runs = list(res.scalars().all())
        print(f"=== RUNS ({len(runs)}) ===")
        for r in runs:
            print(f"Run {r.id}: Iter {r.loop_iteration}, Status: {r.status}, Summary: {r.summary}")
            
        res2 = await db.execute(select(CoverageGap).where(CoverageGap.test_suite_id == suite_id))
        gaps = list(res2.scalars().all())
        print(f"\n=== COVERAGE GAPS ({len(gaps)}) ===")
        for g in gaps:
            print(f"[{g.severity}] {g.scenario_description} (Spawned test: {g.spawned_test_id})")
            
        res3 = await db.execute(select(Test).where(Test.test_suite_id == suite_id).order_by(Test.generation_depth, Test.name))
        tests = list(res3.scalars().all())
        print(f"\n=== TESTS ({len(tests)}) ===")
        for t in tests:
            print(f"[Depth {t.generation_depth}] [{t.scenario_type}] {t.name}")

if __name__ == '__main__':
    asyncio.run(inspect())
