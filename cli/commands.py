"""CLI 命令接口。"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from config.schema import InteractiveConfig, WechatWorkConfig
from config.loader import load_config
from interactive.sync_manager import SyncManager
from interactive.iflow_controller import IFlowController
from interactive.session_monitor import SessionMonitor


app = typer.Typer(
    name="ling-iflow",
    help="Ling-iflow - iflow CLI 交互模式管理工具",
    add_completion=False,
)


@app.command()
def start(
    workspace: str = typer.Option(None, "--workspace", "-w", help="iflow 工作目录"),
    model: str = typer.Option(None, "--model", "-m", help="iflow 模型名称"),
    tmux_session: str = typer.Option(None, "--tmux-session", "-t", help="tmux 会话名称"),
    no_auto_start: bool = typer.Option(False, "--no-auto-start", help="不自动启动 iflow"),
    wechat_enabled: bool = typer.Option(False, "--wechat", help="启用企业微信同步"),
) -> None:
    """启动交互模式服务。
    
    启动 iflow CLI 交互模式，支持企业微信消息同步。
    """
    
    # 配置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    logger.info("=" * 60)
    logger.info("Ling-iflow 交互模式启动中...")
    logger.info("=" * 60)
    
    # 加载配置
    config = load_config()
    
    # 覆盖配置
    if workspace:
        config.workspace = workspace
    if model:
        config.model = model
    if tmux_session:
        config.tmux_session = tmux_session
    if wechat_enabled:
        config.wechat_work.enabled = True
    
    # 显示配置信息
    logger.info(f"工作目录: {config.workspace}")
    logger.info(f"模型: {config.model}")
    logger.info(f"tmux 会话: {config.tmux_session}")
    logger.info(f"企业微信: {'启用' if config.wechat_work.enabled else '禁用'}")
    
    # 创建同步管理器
    sync_manager = SyncManager(
        workspace=config.workspace,
        tmux_session=config.tmux_session,
        wechat_config=config.wechat_work if config.wechat_work.enabled else None,
    )
    
    # 启动服务
    async def run_service():
        try:
            success = await sync_manager.start(auto_start_iflow=not no_auto_start)
            
            if not success:
                logger.error("启动服务失败")
                sys.exit(1)
            
            logger.info("服务已启动，按 Ctrl+C 停止")
            
            # 保持运行
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n收到中断信号，正在停止服务...")
        except Exception as e:
            logger.error(f"服务异常: {e}", exc_info=True)
        finally:
            await sync_manager.stop()
            logger.info("服务已停止")
    
    asyncio.run(run_service())


@app.command()
def stop(
    tmux_session: str = typer.Option("iflow", "--tmux-session", "-t", help="tmux 会话名称"),
) -> None:
    """停止 iflow CLI。
    
    停止运行在 tmux 会话中的 iflow CLI。
    """
    
    controller = IFlowController(tmux_session=tmux_session)
    
    logger.info(f"停止 tmux 会话: {tmux_session}")
    
    if controller.stop_iflow():
        logger.info("已成功停止 iflow CLI")
    else:
        logger.error("停止 iflow CLI 失败")
        sys.exit(1)


@app.command()
def status(
    tmux_session: str = typer.Option("iflow", "--tmux-session", "-t", help="tmux 会话名称"),
    workspace: str = typer.Option("~/.iflow", "--workspace", "-w", help="iflow 工作目录"),
) -> None:
    """查看状态。
    
    查看 iflow CLI 和会话文件的状态。
    """
    
    # 检查 tmux 会话
    controller = IFlowController(tmux_session=tmux_session)
    session_info = controller.get_session_info()
    
    logger.info("=" * 60)
    logger.info("Ling-iflow 状态")
    logger.info("=" * 60)
    logger.info(f"tmux 会话: {tmux_session}")
    logger.info(f"  存在: {'是' if session_info.get('tmux_exists') else '否'}")
    logger.info(f"  iflow 运行中: {'是' if session_info.get('iflow_running') else '否'}")
    
    # 检查会话文件
    monitor = SessionMonitor(workspace=workspace)
    session_files = monitor.find_session_files()
    
    logger.info(f"\n会话文件: {workspace}/projects/")
    logger.info(f"  会话数量: {len(session_files)}")
    
    if session_files:
        logger.info("  会话列表:")
        for i, session_file in enumerate(session_files[:5], 1):
            logger.info(f"    {i}. {session_file.name}")
        
        if len(session_files) > 5:
            logger.info(f"    ... 还有 {len(session_files) - 5} 个会话")


@app.command()
def test(
    simple: bool = typer.Option(False, "--simple", help="运行简单测试"),
) -> None:
    """运行测试程序。
    
    运行企业微信消息模拟测试程序。
    """
    
    # 导入测试模块
    from test_wechat_mock import test_wechat_mock, test_simple
    
    if simple:
        logger.info("运行简单测试...")
        asyncio.run(test_simple())
    else:
        logger.info("运行完整测试...")
        asyncio.run(test_wechat_mock())


@app.command()
def init(
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """初始化配置。
    
    创建默认配置文件。
    """
    
    from config.loader import get_config_path, _create_default_config
    
    if config_path:
        config_file = Path(config_path)
    else:
        config_file = get_config_path()
    
    logger.info(f"创建配置文件: {config_file}")
    
    _create_default_config(config_file)
    
    logger.info(f"配置文件已创建: {config_file}")
    logger.info("请根据需要修改配置文件")


if __name__ == "__main__":
    app()