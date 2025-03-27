import asyncio
import time
from sqlalchemy import select
from database import init_db, get_session, AccountModel


async def migrate_add_id():
    """为现有记录添加ID字段"""
    await init_db()

    async with get_session() as session:
        # 查询所有没有id的记录
        result = await session.execute(
            select(AccountModel).where(AccountModel.id == None)
        )
        accounts = result.scalars().all()

        print(f"找到 {len(accounts)} 条需要更新的记录")

        # 为每条记录添加id
        for i, account in enumerate(accounts):
            # 生成基于索引的间隔时间戳，避免所有记录使用同一时间戳
            timestamp_ms = int(time.time() * 1000) - (len(accounts) - i) * 1000
            account.id = timestamp_ms
            print(f"更新记录 {account.email} 的ID为 {timestamp_ms}")

        await session.commit()
        print("迁移完成")


if __name__ == "__main__":
    asyncio.run(migrate_add_id())
