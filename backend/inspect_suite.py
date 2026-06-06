"""Deep inspection of a test suite for agentic loop analysis."""
import asyncio
from collections import Counter, defaultdict

from sqlalchemy import select

from app.agentic.dedup import compute_generation_hash
from app.db import get_sessionmaker
from app.models import CoverageGap, Run, Test, TestResult

SUITE_ID = "b9995169-4d18-490a-b15e-38d468fca56a"


async def inspect():
    db_maker = get_sessionmaker()
    async with db_maker() as db:
        # Runs
        res = await db.execute(
            select(Run)
            .where(Run.test_suite_id == SUITE_ID)
            .order_by(Run.loop_iteration, Run.started_at)
        )
        runs = list(res.scalars().all())
        print(f"=== RUNS ({len(runs)}) ===")
        for r in runs:
            print(
                f"  iter={r.loop_iteration} id={r.id} status={r.status} "
                f"parent={r.parent_run_id} summary={r.summary}"
            )

        # Tests by depth
        res2 = await db.execute(
            select(Test)
            .where(Test.test_suite_id == SUITE_ID)
            .order_by(Test.generation_depth, Test.scenario_type, Test.name)
        )
        tests = list(res2.scalars().all())
        print(f"\n=== TESTS ({len(tests)}) ===")
        by_depth = Counter(t.generation_depth for t in tests)
        by_scenario = Counter(t.scenario_type for t in tests)
        print(f"  By depth: {dict(by_depth)}")
        print(f"  By scenario_type: {dict(by_scenario)}")
        auto = sum(1 for t in tests if t.auto_generated)
        print(f"  auto_generated: {auto}, baseline: {len(tests) - auto}")

        # Duplicate name analysis
        name_counts = Counter(t.name for t in tests)
        dup_names = {n: c for n, c in name_counts.items() if c > 1}
        if dup_names:
            print(f"\n=== DUPLICATE NAMES ({len(dup_names)}) ===")
            for name, count in sorted(dup_names.items(), key=lambda x: -x[1])[:20]:
                print(f"  [{count}x] {name}")

        # Setup test duplicates
        setup_tests = [t for t in tests if t.scenario_type == "setup"]
        print(f"\n=== SETUP TESTS ({len(setup_tests)}) ===")
        for t in setup_tests:
            print(f"  [depth={t.generation_depth}] {t.name} auto={t.auto_generated}")

        # Semantic near-duplicates (same endpoint + scenario + method + path)
        key_groups = defaultdict(list)
        for t in tests:
            key = (str(t.endpoint_id), t.scenario_type, t.method, t.path)
            key_groups[key].append(t)
        near_dups = {k: v for k, v in key_groups.items() if len(v) > 2}
        if near_dups:
            print(f"\n=== ENDPOINT+SCENARIO GROUPS WITH >2 TESTS ({len(near_dups)}) ===")
            for key, group in sorted(near_dups.items(), key=lambda x: -len(x[1]))[:15]:
                ep, st, m, p = key
                print(f"  [{len(group)}x] {st} {m} {p}")
                for t in group[:5]:
                    print(f"      depth={t.generation_depth} {t.name[:60]}")

        # Hash mismatches (structural hash)
        hash_issues = []
        for t in tests:
            if t.generation_hash:
                expected = compute_generation_hash(
                    t.endpoint_id,
                    t.scenario_type,
                    t.method,
                    t.path,
                    path_params=t.path_params,
                    query_params=t.query_params,
                    body=t.body if isinstance(t.body, dict) else None,
                    expected_status=t.expected_status,
                )
                if t.generation_hash != expected:
                    hash_issues.append(t.name)
        if hash_issues:
            print(f"\n=== HASH MISMATCHES ({len(hash_issues)}) ===")
            for n in hash_issues[:10]:
                print(f"  {n}")

        # Coverage gaps
        res3 = await db.execute(
            select(CoverageGap)
            .where(CoverageGap.test_suite_id == SUITE_ID)
            .order_by(CoverageGap.created_at)
        )
        gaps = list(res3.scalars().all())
        print(f"\n=== COVERAGE GAPS ({len(gaps)}) ===")
        by_run = defaultdict(list)
        for g in gaps:
            by_run[str(g.run_id)].append(g)
        for run_id, run_gaps in by_run.items():
            run_iter = next((r.loop_iteration for r in runs if str(r.id) == run_id), "?")
            print(f"\n  Run iter={run_iter} ({run_id}): {len(run_gaps)} gaps")
            high = [g for g in run_gaps if g.severity == "high"]
            med = [g for g in run_gaps if g.severity == "medium"]
            print(f"    high={len(high)} medium={len(med)}")
            for g in run_gaps:
                spawned = "yes" if g.spawned_test_id else "no"
                print(f"    [{g.severity}] spawned={spawned} {g.scenario_description[:90]}")

        # Duplicate gap descriptions
        gap_desc_counts = Counter(g.scenario_description for g in gaps)
        dup_gaps = {d: c for d, c in gap_desc_counts.items() if c > 1}
        if dup_gaps:
            print(f"\n=== DUPLICATE GAP DESCRIPTIONS ({len(dup_gaps)}) ===")
            for desc, count in sorted(dup_gaps.items(), key=lambda x: -x[1])[:10]:
                print(f"  [{count}x] {desc[:100]}")

        # Test results per run
        print("\n=== TEST RESULTS PER RUN ===")
        for r in runs:
            res4 = await db.execute(
                select(TestResult).where(TestResult.run_id == r.id)
            )
            results = list(res4.scalars().all())
            status_counts = Counter(tr.status for tr in results)
            print(f"  iter={r.loop_iteration} results={len(results)} {dict(status_counts)}")


if __name__ == "__main__":
    asyncio.run(inspect())
