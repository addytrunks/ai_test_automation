import asyncio
import uuid
import logging
from app.runner.router import run_agentic_loop

logging.basicConfig(level=logging.INFO)

async def main():
    suite_id = uuid.UUID('08c46f1b-a12c-43d4-9f11-a2410f2bd18e')
    await run_agentic_loop(suite_id, 'http://localhost:5001')

if __name__ == '__main__':
    asyncio.run(main())
