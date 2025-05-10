import asyncio

async def task1():
    await asyncio.sleep(1)
    print("Task 1 done")

async def task2():
    await asyncio.sleep(1)
    print("Task 2 done")
async def task3():
    await asyncio.sleep(3)
    print("Task 3 done")
async def task4():
    await asyncio.sleep(1)
    print("Task 4 done")
async def task5():
    await asyncio.sleep(1)
    print("Task 5 done")
async def main():
    await asyncio.gather(task1(), task3(), task4(), task5())

asyncio.run(main())
