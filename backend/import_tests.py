import asyncio
import json

from sqlalchemy import select

from app.agentic.dedup import compute_generation_hash
from app.db import get_sessionmaker
from app.models import Endpoint, Project, Spec, Test, TestSuite


async def import_tests(
    *,
    json_path: str = "baseline_tests.json",
    suite_name: str = "Baseline Tests Import",
) -> None:
    db_maker = get_sessionmaker()

    async with db_maker() as db:
        proj_res = await db.execute(select(Project))
        project = proj_res.scalars().first()
        if not project:
            print("No projects found!")
            return

        spec_res = await db.execute(select(Spec).where(Spec.project_id == project.id))
        spec = spec_res.scalars().first()
        if not spec:
            print("No spec found for project!")
            return

        new_suite = TestSuite(
            project_id=project.id,
            spec_id=spec.id,
            name=suite_name,
            status="ready",
        )
        db.add(new_suite)
        await db.commit()
        await db.refresh(new_suite)
        print(f"Created new suite {new_suite.id} ({suite_name})")

        res = await db.execute(select(Endpoint).where(Endpoint.spec_id == spec.id))
        endpoints = res.scalars().all()
        ep_map = {f"{e.method.upper()}_{e.path}": e.id for e in endpoints}

        with open(json_path, encoding="utf-8") as f:
            test_dicts = json.load(f)

        imported = 0
        for td in test_dicts:
            ep_key = f"{td['method'].upper()}_{td['path']}"
            ep_id = ep_map.get(ep_key)
            if not ep_id:
                print(f"Warning: Endpoint not found for {ep_key}, skipping")
                continue

            gen_hash = compute_generation_hash(
                ep_id,
                td["scenario_type"],
                td["method"],
                td["path"],
                path_params=td.get("path_params"),
                query_params=td.get("query_params"),
                body=td.get("body"),
                expected_status=td.get("expected_status"),
                name=td.get("name"),
            )

            test = Test(
                test_suite_id=new_suite.id,
                endpoint_id=ep_id,
                name=td["name"],
                description=td.get("description"),
                scenario_type=td["scenario_type"],
                method=td["method"],
                path=td["path"],
                headers=td.get("headers"),
                body=td.get("body"),
                path_params=td.get("path_params"),
                query_params=td.get("query_params"),
                expected_status=td.get("expected_status"),
                assertions=td.get("assertions", []),
                extract=td.get("extract"),
                static_context=td.get("static_context"),
                generation_depth=0,
                auto_generated=False,
                generation_hash=gen_hash,
            )
            db.add(test)
            imported += 1

        await db.commit()
        print(f"Successfully imported {imported} tests into TestSuite {new_suite.id}")


if __name__ == "__main__":
    asyncio.run(import_tests())
