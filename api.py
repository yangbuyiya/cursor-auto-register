from fastapi import FastAPI, HTTPException, Depends, status, Body
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, desc
from pathlib import Path
from database import get_session, AccountModel, init_db
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uvicorn
import asyncio
import os
import traceback
from fastapi.responses import JSONResponse, FileResponse
from cursor_pro_keep_alive import main as register_account
from browser_utils import BrowserManager
from logger import info, error
from tokenManager.oneapi_cursor_cleaner import handle_oneapi_cursor_channel
from tokenManager.oneapi_manager import OneAPIManager
from contextlib import asynccontextmanager
from tokenManager.cursor import Cursor  # 添加这个导入
import concurrent.futures
from functools import lru_cache
from config import MAX_ACCOUNTS, REGISTRATION_INTERVAL, API_HOST, API_PORT, API_DEBUG, API_WORKERS
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# 全局状态追踪
registration_status = {
    "is_running": False,
    "last_run": None,
    "last_status": None,
    "next_run": None,
    "total_runs": 0,
    "successful_runs": 0,
    "failed_runs": 0,
}

# 定义静态文件目录
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)  # 确保目录存在

# 全局任务存储
background_tasks = {"registration_task": None}

# 添加lifespan管理器，在应用启动时初始化数据库
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    await init_db()
    info("数据库已初始化")
    yield
    # 关闭时的清理操作
    info("应用程序关闭")


app = FastAPI(
    title="Cursor Account API",
    description="API for managing Cursor accounts",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=API_DEBUG,
)


# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# 使用startup事件初始化数据库
@app.on_event("startup")
async def startup_event():
    await init_db()
    info("数据库已初始化")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Account(BaseModel):
    email: str
    password: Optional[str] = None
    token: str
    user: str
    usage_limit: Optional[str] = None
    created_at: Optional[str] = None
    status: str = "active"  # 默认为"active"
    id: Optional[int] = None  # 添加id字段，可选

    class Config:
        from_attributes = True


class AccountResponse(BaseModel):
    success: bool
    data: Optional[Account] = None
    message: str = ""

async def get_active_account_count() -> int:
    """获取当前账号总数"""
    async with get_session() as session:
        result = await session.execute(select(func.count()).select_from(AccountModel).where(AccountModel.status == "active"))
        return result.scalar()

async def get_account_count() -> int:
    """获取当前账号总数"""
    async with get_session() as session:
        result = await session.execute(select(func.count()).select_from(AccountModel))
        return result.scalar()


async def run_registration():
    """运行注册脚本"""
    global registration_status
    browser_manager = None

    try:
        info("注册任务开始运行")

        while registration_status["is_running"]:
            try:
                count = await get_active_account_count()
                info(f"当前数据库已激活账号数: {count}")
                
                if count >= MAX_ACCOUNTS:
                    # 修改：不再结束任务，而是进入监控模式
                    info(f"已达到最大账号数量 ({count}/{MAX_ACCOUNTS})，进入监控模式")
                    registration_status["last_status"] = "monitoring"
                    
                    # 等待检测间隔时间
                    next_check = datetime.now().timestamp() + REGISTRATION_INTERVAL
                    registration_status["next_run"] = next_check
                    info(f"将在 {REGISTRATION_INTERVAL} 秒后重新检查账号数量")
                    await asyncio.sleep(REGISTRATION_INTERVAL)
                    
                    # 跳过当前循环的剩余部分，继续下一次循环检查
                    continue

                info(f"开始注册尝试 (当前账号数: {count}/{MAX_ACCOUNTS})")
                registration_status["last_run"] = datetime.now().isoformat()
                registration_status["total_runs"] += 1

                # 初始化浏览器管理器
                if not browser_manager:
                    browser_manager = BrowserManager()
                    if not browser_manager.init_browser():
                        error("浏览器初始化失败，终止注册任务")
                        registration_status["failed_runs"] += 1
                        registration_status["last_status"] = "error"
                        registration_status["is_running"] = False
                        break

                # 调用注册函数
                try:
                    success = await asyncio.get_event_loop().run_in_executor(
                        None, register_account
                    )

                    if success:
                        registration_status["successful_runs"] += 1
                        registration_status["last_status"] = "success"
                        info("注册成功")
                    else:
                        registration_status["failed_runs"] += 1
                        registration_status["last_status"] = "failed"
                        info("注册失败")
                except SystemExit:
                    # 捕获 SystemExit 异常，这是注册脚本正常退出的方式
                    info("注册脚本正常退出")
                    if registration_status["last_status"] != "error":
                        registration_status["last_status"] = "completed"
                except Exception as e:
                    error(f"注册过程执行出错: {str(e)}")
                    error(traceback.format_exc())
                    registration_status["failed_runs"] += 1
                    registration_status["last_status"] = "error"

                # 更新下次运行时间
                next_run = datetime.now().timestamp() + REGISTRATION_INTERVAL
                registration_status["next_run"] = next_run

                info(f"等待 {REGISTRATION_INTERVAL} 秒后进行下一次尝试")
                await asyncio.sleep(REGISTRATION_INTERVAL)

            except asyncio.CancelledError:
                info("注册迭代被取消")
                raise
            except Exception as e:
                registration_status["failed_runs"] += 1
                registration_status["last_status"] = "error"
                error(f"注册过程出错: {str(e)}")
                error(traceback.format_exc())
                if not registration_status["is_running"]:
                    break
                await asyncio.sleep(REGISTRATION_INTERVAL)
    except asyncio.CancelledError:
        info("注册任务被取消")
        raise
    except Exception as e:
        error(f"注册任务致命错误: {str(e)}")
        error(traceback.format_exc())
        raise
    finally:
        registration_status["is_running"] = False
        if browser_manager:
            try:
                browser_manager.quit()
            except Exception as e:
                error(f"清理浏览器资源时出错: {str(e)}")
                error(traceback.format_exc())

@app.get("/", tags=["UI"])
async def serve_index():
    """提供Web UI界面"""
    index_path = Path(__file__).parent / "index.html"
    return FileResponse(index_path)


@app.get("/general", tags=["General"])
async def root():
    """API根路径，返回API信息"""
    try:
        # 获取当前账号数量和使用情况
        async with get_session() as session:
            result = await session.execute(select(AccountModel))
            accounts = result.scalars().all()

            usage_info = []
            total_balance = 0
            active_accounts = 0

            for acc in accounts:
                remaining_balance = Cursor.get_remaining_balance(acc.user, acc.token)
                remaining_days = Cursor.get_trial_remaining_days(acc.user, acc.token)

                if remaining_balance is not None and remaining_balance > 0:
                    active_accounts += 1
                    total_balance += remaining_balance

                usage_info.append(
                    {
                        "email": acc.email,
                        "balance": remaining_balance,
                        "days": remaining_days,
                        "status": (
                            "active"
                            if remaining_balance is not None and remaining_balance > 0
                            else "inactive"
                        ),
                    }
                )

        return {
            "service": {
                "name": "Cursor Account API",
                "version": "1.0.0",
                "status": "running",
                "description": "API for managing Cursor Pro accounts and automatic registration",
            },
            "statistics": {
                "total_accounts": len(accounts),
                "active_accounts": active_accounts,
                "total_remaining_balance": total_balance,
                "max_accounts": MAX_ACCOUNTS,
                "remaining_slots": MAX_ACCOUNTS - len(accounts),
                "registration_interval": f"{REGISTRATION_INTERVAL} seconds",
            },
            "accounts_info": usage_info,  # 添加账号详细信息
            "registration_status": {
                "is_running": registration_status["is_running"],
                "last_run": registration_status["last_run"],
                "last_status": registration_status["last_status"],
                "next_run": registration_status["next_run"],
                "statistics": {
                    "total_runs": registration_status["total_runs"],
                    "successful_runs": registration_status["successful_runs"],
                    "failed_runs": registration_status["failed_runs"],
                    "success_rate": (
                        f"{(registration_status['successful_runs'] / registration_status['total_runs'] * 100):.1f}%"
                        if registration_status["total_runs"] > 0
                        else "N/A"
                    ),
                },
            },
            "endpoints": {
                "documentation": {"swagger": "/docs", "redoc": "/redoc"},
                "health": {
                    "check": "/health",
                    "registration_status": "/registration/status",
                },
                "accounts": {
                    "list_all": "/accounts",
                    "random": "/account/random",
                    "create": {"path": "/account", "method": "POST"},
                    "delete": {"path": "/account/{email}", "method": "DELETE"},
                    "usage": {
                        "path": "/account/{email}/usage",
                        "method": "GET",
                        "description": "Get account usage by email",
                    },
                },
                "registration": {
                    "start": {"path": "/registration/start", "method": "GET"},
                    "stop": {"path": "/registration/stop", "method": "POST"},
                    "status": {"path": "/registration/status", "method": "GET"},
                },
                "usage": {"check": {"path": "/usage", "method": "GET"}},
                "clean": {
                    "run": {
                        "path": "/clean",
                        "method": "POST",
                        "params": {"clean_type": ["check", "disable", "delete"]},
                    }
                },
            },
            "support": {
                "github": "https://github.com/Elawen-Carl/cursor-account-api",
                "author": "Elawen Carl",
                "contact": "elawencarl@gmail.com",
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        error(f"根端点错误: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching API information",
        )


@app.get("/health", tags=["General"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@app.get("/accounts", response_model=List[Account], tags=["Accounts"])
async def get_accounts(status: Optional[str] = None):
    """获取所有可用的账号和token
    
    可选参数 status 用于过滤账号状态:
    - active: 只返回正常账号
    - disabled: 只返回停用账号
    - deleted: 只返回已删除账号
    - 不提供参数则返回所有账号
    
    结果按id降序排列（最新的账号排在前面）
    """
    try:
        async with get_session() as session:
            # 构建基本查询，添加按id降序排序
            query = select(AccountModel).order_by(desc(AccountModel.id))
            
            # 根据状态过滤
            if status:
                query = query.where(AccountModel.status == status)
                
            result = await session.execute(query)
            accounts = result.scalars().all()

            if not accounts:
                raise HTTPException(status_code=404, detail="没有找到符合条件的账号")
            return accounts
    except Exception as e:
        error(f"获取账号失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="服务器内部错误")


@app.get("/account/random", response_model=AccountResponse, tags=["Accounts"])
async def get_random_account():
    """随机获取一个可用的账号和token"""
    try:
        async with get_session() as session:
            result = await session.execute(
                select(AccountModel).order_by(func.random()).limit(1)
            )
            account = result.scalar_one_or_none()

            if not account:
                return AccountResponse(success=False, message="No accounts available")

            return AccountResponse(success=True, data=Account.from_orm(account))
    except Exception as e:
        error(f"获取随机账号失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/account", response_model=AccountResponse, tags=["Accounts"])
async def create_account(account: Account):
    """创建新账号"""
    try:
        async with get_session() as session:
            db_account = AccountModel(
                email=account.email,
                password=account.password,
                token=account.token,
                usage_limit=account.usage_limit,
                created_at=account.created_at,
            )
            session.add(db_account)
            await session.commit()
            return AccountResponse(
                success=True, data=account, message="Account created successfully"
            )
    except Exception as e:
        error(f"创建账号失败: {str(e)}")
        error(traceback.format_exc())
        return AccountResponse(
            success=False, message=f"Failed to create account: {str(e)}"
        )


@app.delete("/account/{email}", response_model=AccountResponse, tags=["Accounts"])
async def delete_account(email: str, hard_delete: bool = False):
    """删除或停用指定邮箱的账号
    
    如果 hard_delete=True，则物理删除账号
    否则仅将状态设置为'deleted'
    """
    try:
        async with get_session() as session:
            # 先检查账号是否存在
            result = await session.execute(
                select(AccountModel).where(AccountModel.email == email)
            )
            account = result.scalar_one_or_none()

            if not account:
                return AccountResponse(
                    success=False, message=f"账号 {email} 不存在"
                )

            if hard_delete:
                # 物理删除账号
                await session.execute(
                    delete(AccountModel).where(AccountModel.email == email)
                )
                delete_message = f"账号 {email} 已永久删除"
            else:
                # 逻辑删除：将状态更新为'deleted'
                account.status = "deleted"
                delete_message = f"账号 {email} 已标记为删除状态"
                
            await session.commit()
            
            return AccountResponse(
                success=True, message=delete_message
            )
    except Exception as e:
        error(f"删除账号失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除账号失败: {str(e)}",
        )


# 添加状态更新的请求体模型
class StatusUpdate(BaseModel):
    status: str

@app.put("/account/id/{id}/status", response_model=AccountResponse, tags=["Accounts"])
async def update_account_status(id: str, update: StatusUpdate):
    """更新账号状态
    
    可选状态: active (正常), disabled (停用), deleted (已删除)
    """
    # 使用update.status替代原先的status参数
    try:
        # 验证状态值
        valid_statuses = ["active", "disabled", "deleted"]
        if update.status not in valid_statuses:
            return AccountResponse(
                success=False, 
                message=f"无效的状态值。允许的值: {', '.join(valid_statuses)}"
            )
            
        async with get_session() as session:
            # 通过邮箱查询账号
            result = await session.execute(
                select(AccountModel).where(AccountModel.id == id)
            )
            account = result.scalar_one_or_none()

            if not account:
                return AccountResponse(
                    success=False, message=f"邮箱为 {email} 的账号不存在"
                )

            # 更新状态
            account.status = update.status
            await session.commit()

            return AccountResponse(
                success=True, message=f"账号 {account.email} 状态已更新为 '{update.status}'"
            )
    except Exception as e:
        error(f"通过邮箱更新账号状态失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新账号状态失败: {str(e)}",
        )


@app.get("/registration/start", tags=["Registration"])
async def start_registration():
    """手动启动注册任务"""
    info("手动启动注册任务")
    global background_tasks, registration_status
    try:
        # 检查是否已达到最大账号数
        count = await get_active_account_count()
        
        # 检查任务是否已在运行
        if (
            background_tasks["registration_task"]
            and not background_tasks["registration_task"].done()
        ):
            # 确定当前状态
            current_status = "monitoring" if registration_status["last_status"] == "monitoring" else "running"
            
            status_message = (
                f"注册任务已在运行中 (状态: {current_status})" if current_status == "running"
                else f"已达到最大账号数量({count}/{MAX_ACCOUNTS})，正在监控账号状态，当账号数量减少时将自动继续注册"
            )
            
            info(f"注册请求被忽略 - 任务已在{current_status}状态")
            return {
                "success": True,
                "message": status_message,
                "status": {
                    "is_running": registration_status["is_running"],
                    "last_run": registration_status["last_run"],
                    "next_run": (
                        datetime.fromtimestamp(
                            registration_status["next_run"]
                        ).isoformat()
                        if registration_status["next_run"]
                        else None
                    ),
                    "last_status": registration_status["last_status"],
                    "current_count": count,
                    "max_accounts": MAX_ACCOUNTS,
                },
            }

        # 重置注册状态
        registration_status.update(
            {
                "is_running": True,
                "last_status": "starting",
                "last_run": datetime.now().isoformat(),
                "next_run": datetime.now().timestamp() + REGISTRATION_INTERVAL,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
            }
        )

        # 创建并启动新任务
        loop = asyncio.get_running_loop()
        task = loop.create_task(run_registration())
        background_tasks["registration_task"] = task

        # 添加任务完成回调
        def task_done_callback(task):
            try:
                task.result()  # 这将重新引发任何未处理的异常
            except asyncio.CancelledError:
                info("注册任务被取消")
                registration_status["last_status"] = "cancelled"
            except Exception as e:
                error(f"注册任务失败: {str(e)}")
                error(traceback.format_exc())
                registration_status["last_status"] = "error"
            finally:
                if registration_status["is_running"]:  # 只有在任务仍在运行时才更新状态
                    registration_status["is_running"] = False
                background_tasks["registration_task"] = None

        task.add_done_callback(task_done_callback)
        info("手动启动注册任务")

        # 等待任务实际开始运行
        await asyncio.sleep(1)

        # 检查任务是否成功启动
        if task.done():
            try:
                task.result()  # 如果任务已完成，检查是否有异常
            except Exception as e:
                error(f"注册任务启动失败: {str(e)}")
                error(traceback.format_exc())
                registration_status["is_running"] = False
                registration_status["last_status"] = "error"
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start registration task: {str(e)}",
                )

        # 检查是否已达到最大账号数，预先设置为监控模式
        if count >= MAX_ACCOUNTS:
            registration_status["last_status"] = "monitoring"
            status_message = f"已达到最大账号数量({count}/{MAX_ACCOUNTS})，进入监控模式，当账号数量减少时将自动继续注册"
        else:
            status_message = "注册任务启动成功"

        return {
            "success": True,
            "message": status_message,
            "status": {
                "is_running": registration_status["is_running"],
                "last_run": registration_status["last_run"],
                "next_run": datetime.fromtimestamp(
                    registration_status["next_run"]
                ).isoformat(),
                "last_status": registration_status["last_status"],
                "current_count": count,
                "max_accounts": MAX_ACCOUNTS,
            },
        }
    except Exception as e:
        error(f"启动注册任务失败: {str(e)}")
        error(traceback.format_exc())
        registration_status["is_running"] = False
        registration_status["last_status"] = "error"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start registration task: {str(e)}",
        )


@app.get("/registration/stop", tags=["Registration"])
async def stop_registration():
    """手动停止注册任务"""
    global background_tasks
    try:
        if (
            not background_tasks["registration_task"]
            or background_tasks["registration_task"].done()
        ):
            return {"success": False, "message": "No running registration task found"}

        background_tasks["registration_task"].cancel()
        try:
            await background_tasks["registration_task"]
        except asyncio.CancelledError:
            info("注册任务被取消")

        background_tasks["registration_task"] = None
        registration_status["is_running"] = False
        registration_status["last_status"] = "manually stopped"

        return {"success": True, "message": "Registration task stopped successfully"}
    except Exception as e:
        error(f"停止注册任务失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop registration task: {str(e)}",
        )


@app.get("/registration/status", tags=["Registration"])
async def get_registration_status():
    """获取注册状态"""
    try:
        count = await get_account_count()
        active_count = await get_active_account_count()  # 添加获取活跃账号数
        
        # 更新任务状态逻辑
        if background_tasks["registration_task"] and not background_tasks["registration_task"].done():
            if registration_status["last_status"] == "monitoring":
                task_status = "monitoring"  # 新增监控状态
            else:
                task_status = "running"
        else:
            task_status = "stopped"

        status_info = {
            "current_count": count,
            "active_count": active_count,  # 添加活跃账号数
            "max_accounts": MAX_ACCOUNTS,
            "is_registration_active": active_count < MAX_ACCOUNTS,
            "remaining_slots": MAX_ACCOUNTS - active_count,
            "task_status": task_status,
            "registration_details": {
                "is_running": registration_status["is_running"],
                "last_run": registration_status["last_run"],
                "last_status": registration_status["last_status"],
                "next_run": registration_status["next_run"],
                "statistics": {
                    "total_runs": registration_status["total_runs"],
                    "successful_runs": registration_status["successful_runs"],
                    "failed_runs": registration_status["failed_runs"],
                    "success_rate": (
                        f"{(registration_status['successful_runs'] / registration_status['total_runs'] * 100):.1f}%"
                        if registration_status["total_runs"] > 0
                        else "N/A"
                    ),
                },
            },
        }

        # 添加状态解释信息
        if task_status == "monitoring":
            status_info["status_message"] = f"已达到最大账号数量({active_count}/{MAX_ACCOUNTS})，正在监控账号状态，当账号数量减少时将自动继续注册"
        elif task_status == "running":
            status_info["status_message"] = f"正在执行注册流程，当前账号数：{active_count}/{MAX_ACCOUNTS}"
        else:
            status_info["status_message"] = "注册任务未运行"

        info(f"请求注册状态 (当前账号数: {count}, 活跃账号数: {active_count}, 状态: {task_status})")
        return status_info

    except Exception as e:
        error(f"获取注册状态失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get registration status: {str(e)}",
        )


# 自定义异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    error(f"HTTP错误发生: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code, content={"success": False, "message": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    error(f"意外错误发生: {str(exc)}")
    error(f"错误详情: {traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error occurred",
            "detail": str(exc) if app.debug else None,
        },
    )


# 添加缓存装饰器
@lru_cache(maxsize=100)
def get_account_status(user: str, token: str, timestamp: int):
    """缓存10分钟内的账号状态"""
    balance = Cursor.get_remaining_balance(user, token)
    days = Cursor.get_trial_remaining_days(user, token)
    return {
        "balance": balance,
        "days": days,
        "status": "active" if balance is not None and balance > 0 else "inactive",
    }


# 修改 check_usage 接口
@app.get("/usage")
async def check_usage():
    try:
        async with get_session() as session:
            result = await session.execute(select(AccountModel))
            accounts = result.scalars().all()

            # 使用当前时间的10分钟间隔作为缓存key
            cache_timestamp = int(datetime.now().timestamp() / 600)

            # 使用线程池并发获取账号状态
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(
                        get_account_status, acc.user, acc.token, cache_timestamp
                    )
                    for acc in accounts
                ]

                usage_info = []
                for acc, future in zip(accounts, futures):
                    status = future.result()
                    usage_info.append(
                        {
                            "email": acc.email,
                            "usage_limit": status["balance"],
                            "remaining_days": status["days"],
                            "status": status["status"],
                        }
                    )

            return {
                "total_accounts": len(accounts),
                "usage_info": usage_info,
                "summary": {
                    "active_accounts": sum(
                        1 for info in usage_info if info["status"] == "active"
                    ),
                    "inactive_accounts": sum(
                        1 for info in usage_info if info["status"] == "inactive"
                    ),
                    "total_remaining_balance": sum(
                        info["usage_limit"] or 0 for info in usage_info
                    ),
                },
            }
    except Exception as e:
        error(f"检查使用量失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/account/{email}/usage", tags=["Accounts"])
async def get_account_usage(email: str):
    """根据邮箱查询账户使用量并更新数据库"""
    try:
        async with get_session() as session:
            # 查询指定邮箱的账号
            result = await session.execute(
                select(AccountModel).where(AccountModel.email == email)
            )
            account = result.scalar_one_or_none()

            if not account:
                raise HTTPException(
                    status_code=404, detail=f"Account with email {email} not found"
                )

            # 获取账号使用量
            remaining_balance = Cursor.get_remaining_balance(
                account.user, account.token
            )
            remaining_days = Cursor.get_trial_remaining_days(
                account.user, account.token
            )
            
            # 计算总额度和已使用额度
            total_limit = 150  # 默认总额度
            used_limit = 0
            
            if remaining_balance is not None:
                used_limit = total_limit - remaining_balance
                if remaining_days is not None and remaining_days == 0:
                    account.status = "disabled"

                # 更新数据库中的usage_limit字段
                account.usage_limit = str(remaining_balance)
                await session.commit()
                db_updated = True
            else:
                db_updated = False

            return {
                "success": True,
                "email": account.email,
                "usage": {
                    "remaining_balance": remaining_balance,
                    "total_limit": total_limit,
                    "used_limit": used_limit,
                    "remaining_days": remaining_days,
                    "status": (
                        "active"
                        if remaining_balance is not None and remaining_balance > 0
                        else "inactive"
                    ),
                },
                "db_updated": db_updated,
                "timestamp": datetime.now().isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        error(f"查询账号使用量失败: {str(e)}")
        error(traceback.format_exc())
        return {
            "success": False,
            "message": f"Failed to get account usage: {str(e)}"
        }

# 添加通过ID删除账号的API
@app.delete("/account/id/{id}", response_model=AccountResponse, tags=["Accounts"])
async def delete_account_by_id(id: int, hard_delete: bool = False):
    """通过ID删除或停用账号
    
    如果 hard_delete=True，则物理删除账号
    否则仅将状态设置为'deleted'
    """
    try:
        async with get_session() as session:
            # 通过ID查询账号
            result = await session.execute(
                select(AccountModel).where(AccountModel.id == id)
            )
            account = result.scalar_one_or_none()

            if not account:
                return AccountResponse(
                    success=False, message=f"ID为 {id} 的账号不存在"
                )

            email = account.email  # 保存邮箱以在响应中显示

            if hard_delete:
                # 物理删除账号
                await session.execute(
                    delete(AccountModel).where(AccountModel.id == id)
                )
                delete_message = f"账号 {email} (ID: {id}) 已永久删除"
            else:
                # 逻辑删除：将状态更新为'deleted'
                account.status = "deleted"
                delete_message = f"账号 {email} (ID: {id}) 已标记为删除状态"
                
            await session.commit()
            
            return AccountResponse(
                success=True, message=delete_message
            )
    except Exception as e:
        error(f"通过ID删除账号失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除账号失败: {str(e)}",
        )

# 添加"使用Token"功能
@app.post("/account/use-token/{id}", tags=["Accounts"])
async def use_account_token(id: int):
    """使用指定账号的Token更新Cursor认证"""
    try:
        async with get_session() as session:
            # 通过ID查询账号
            result = await session.execute(
                select(AccountModel).where(AccountModel.id == id)
            )
            account = result.scalar_one_or_none()

            if not account:
                return {"success": False, "message": f"ID为 {id} 的账号不存在"}
                
            # 调用CursorAuthManager更新认证
            from cursor_auth_manager import CursorAuthManager
            auth_manager = CursorAuthManager()
            success = auth_manager.update_auth(email=account.email, access_token=account.token, refresh_token=account.token)
            # 重置Cursor的机器ID
            from cursor_shadow_patcher import CursorShadowPatcher
            resetter = CursorShadowPatcher()
            patch_success = resetter.reset_machine_ids()
            
            if success and patch_success:
                return {"success": True, "message": f"成功使用账号 {account.email} 的Token并重置了机器ID"}
            elif success:
                return {"success": True, "message": f"成功使用账号 {account.email} 的Token，但机器ID重置失败"}
            else:
                return {"success": False, "message": "Token更新失败"}
                
    except Exception as e:
        error(f"使用账号Token失败: {str(e)}")
        error(traceback.format_exc())
        return {"success": False, "message": f"使用Token失败: {str(e)}"}

# 添加配置相关模型
class ConfigModel(BaseModel):
    BROWSER_HEADLESS: bool
    BROWSER_USER_AGENT: str
    MAX_ACCOUNTS: int
    EMAIL_DOMAINS: str
    EMAIL_USERNAME: str
    EMAIL_PIN: str
    BROWSER_PATH: Optional[str] = None
    CURSOR_PATH: Optional[str] = None

# 获取配置端点
@app.get("/config", tags=["Config"])
async def get_config():
    """获取当前系统配置"""
    try:
        # 重新加载配置以确保获取最新值
        load_dotenv()
        
        config = {
            "BROWSER_HEADLESS": os.getenv("BROWSER_HEADLESS", "True").lower() == "true",
            "BROWSER_USER_AGENT": os.getenv("BROWSER_USER_AGENT", ""),
            "MAX_ACCOUNTS": int(os.getenv("MAX_ACCOUNTS", "10")),
            "EMAIL_DOMAINS": os.getenv("EMAIL_DOMAINS", ""),
            "EMAIL_USERNAME": os.getenv("EMAIL_USERNAME", ""),
            "EMAIL_PIN": os.getenv("EMAIL_PIN", ""),
            "BROWSER_PATH": os.getenv("BROWSER_PATH", ""),
            "CURSOR_PATH": os.getenv("CURSOR_PATH", "")
        }
        
        return {"success": True, "data": config}
    except Exception as e:
        error(f"获取配置失败: {str(e)}")
        error(traceback.format_exc())
        return {"success": False, "message": f"获取配置失败: {str(e)}"}

# 更新配置端点
@app.put("/config", tags=["Config"])
async def update_config(config: ConfigModel):
    """更新系统配置"""
    try:
        # 获取.env文件路径
        env_path = Path(__file__).parent / ".env"
        
        # 读取当前.env文件内容
        current_lines = []
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                current_lines = f.readlines()
        
        # 构建配置字典
        config_dict = {
            "BROWSER_HEADLESS": str(config.BROWSER_HEADLESS),
            "BROWSER_USER_AGENT": config.BROWSER_USER_AGENT,
            "MAX_ACCOUNTS": str(config.MAX_ACCOUNTS),
            "EMAIL_DOMAINS": config.EMAIL_DOMAINS,
            "EMAIL_USERNAME": config.EMAIL_USERNAME,
            "EMAIL_PIN": config.EMAIL_PIN
        }
        
        # 添加可选配置（如果提供）
        if config.BROWSER_PATH:
            config_dict["BROWSER_PATH"] = config.BROWSER_PATH
        if config.CURSOR_PATH:
            config_dict["CURSOR_PATH"] = config.CURSOR_PATH
        
        # 处理现有行或创建新行
        updated_lines = []
        updated_keys = set()
        
        for line in current_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                updated_lines.append(line)
                continue
                
            key, value = line.split("=", 1) if "=" in line else (line, "")
            key = key.strip()
            
            if key in config_dict:
                updated_lines.append(f"{key}={config_dict[key]}")
                updated_keys.add(key)
            else:
                updated_lines.append(line)
        
        # 添加未更新的配置项
        for key, value in config_dict.items():
            if key not in updated_keys and value:
                updated_lines.append(f"{key}={value}")
        
        # 写入更新后的配置
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(updated_lines))
        
        # 重新加载环境变量
        load_dotenv(override=True)
        
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        error(f"更新配置失败: {str(e)}")
        error(traceback.format_exc())
        return {"success": False, "message": f"更新配置失败: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_DEBUG,
        access_log=True,
        log_level="info",
        workers=API_WORKERS,
        loop="asyncio",  # Windows下使用默认的asyncio
    )
