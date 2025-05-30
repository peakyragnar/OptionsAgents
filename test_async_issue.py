#!/usr/bin/env python
"""Test async task creation issue"""
import asyncio

async def task1():
    print("Task 1 started")
    while True:
        print("Task 1 running...")
        await asyncio.sleep(2)

async def task2():
    print("Task 2 started")  # This should print if task starts
    while True:
        print("Task 2 running...")
        await asyncio.sleep(2)

async def main():
    print("Creating tasks...")
    
    # Method 1: Direct task creation
    tasks = [
        asyncio.create_task(task1()),
        asyncio.create_task(task2())
    ]
    print(f"Created {len(tasks)} tasks")
    
    # Wait a bit to see output
    await asyncio.sleep(5)
    
    # Cancel tasks
    for task in tasks:
        task.cancel()

if __name__ == "__main__":
    asyncio.run(main())