"""
Test Common Components

测试通用组件（MessageConverter 和 NotificationManager）。
"""

import pytest
import asyncio

from src.core.message import Message, MessageContent, MessageType
from src.modules.common.converter import MessageConverter
from src.modules.common.notifications import NotificationManager


class TestMessageConverter:
    """测试消息转换器"""
    
    def test_converter_initialization(self):
        """测试转换器初始化"""
        converter = MessageConverter()
        assert converter is not None
        assert len(converter._inbound_converters) == 0
        assert len(converter._outbound_converters) == 0
    
    def test_create_wechat_inbound_message(self):
        """测试创建企业微信入站消息"""
        converter = MessageConverter()
        
        wechat_msg = {
            "content": "测试消息",
            "chat_id": "test_chat",
            "sender_id": "test_user",
            "is_group": False,
            "msg_type": "text"
        }
        
        message = converter.create_wechat_inbound_message(wechat_msg, "test_module")
        
        assert message is not None
        assert message.type == MessageType.TEXT
        assert message.content.text == "测试消息"
        assert message.from_module == "test_module"
        assert message.chat_id == "test_chat"
        assert message.user_id == "test_user"
        assert message.is_group is False
        assert message.metadata["msg_type"] == "text"
    
    def test_create_wechat_outbound_message(self):
        """测试创建企业微信出站消息"""
        converter = MessageConverter()
        
        message = Message(
            id="test_id",
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text="回复消息"),
            from_module="test_module",
            chat_id="test_chat",
            is_group=False
        )
        
        platform_msg = converter.create_wechat_outbound_message(message)
        
        assert platform_msg is not None
        assert platform_msg["content"] == "回复消息"
        assert platform_msg["chat_id"] == "test_chat"
        assert platform_msg["is_group"] is False
        assert platform_msg["msg_type"] == "text"
    
    def test_create_iflow_inbound_message(self):
        """测试创建 iflow 入站消息"""
        converter = MessageConverter()
        
        iflow_msg = {
            "content": "iflow 测试消息",
            "chat_id": "test_chat",
            "user_id": "test_user",
            "is_group": False,
            "source": "wechat",
            "scope": "reply_only"
        }
        
        message = converter.create_iflow_inbound_message(iflow_msg, "test_module")
        
        assert message is not None
        assert message.type == MessageType.TEXT
        assert message.content.text == "iflow 测试消息"
        assert message.from_module == "test_module"
        assert message.chat_id == "test_chat"
        assert message.user_id == "test_user"
        assert message.is_group is False
        assert message.metadata["msg_type"] == "iflow_request"
        assert message.metadata["source"] == "wechat"
        assert message.metadata["scope"] == "reply_only"
    
    def test_create_iflow_outbound_message(self):
        """测试创建 iflow 出站消息"""
        converter = MessageConverter()
        
        message = Message(
            id="test_id",
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text="iflow 回复"),
            from_module="test_module",
            metadata={
                "chat_id": "test_chat",
                "user_id": "test_user",
                "is_group": False,
                "receiver": "wechat",
                "scope": "reply_only",
                "reply_type": "reply"
            }
        )
        
        platform_msg = converter.create_iflow_outbound_message(message)
        
        assert platform_msg is not None
        assert platform_msg["content"] == "iflow 回复"
        assert platform_msg["chat_id"] == "test_chat"
        assert platform_msg["user_id"] == "test_user"
        assert platform_msg["is_group"] is False
        assert platform_msg["receiver"] == "wechat"
        assert platform_msg["scope"] == "reply_only"
        assert platform_msg["reply_type"] == "reply"
    
    def test_register_inbound_converter(self):
        """测试注册入站转换器"""
        converter = MessageConverter()
        
        def custom_converter(msg):
            return Message(
                id="custom_id",
                type=MessageType.TEXT,
                content=MessageContent(type=MessageType.TEXT, text=msg.get("content", "")),
                from_module="custom_module"
            )
        
        converter.register_inbound_converter("custom", custom_converter)
        
        assert "custom" in converter._inbound_converters
        assert converter._inbound_converters["custom"] == custom_converter
    
    def test_register_outbound_converter(self):
        """测试注册出站转换器"""
        converter = MessageConverter()
        
        def custom_converter(msg):
            return {"content": msg.content.text}
        
        converter.register_outbound_converter("custom", custom_converter)
        
        assert "custom" in converter._outbound_converters
        assert converter._outbound_converters["custom"] == custom_converter


class TestNotificationManager:
    """测试通知管理器"""
    
    def test_notification_manager_initialization(self):
        """测试通知管理器初始化"""
        manager = NotificationManager()
        assert manager is not None
        assert len(manager._notification_handlers) == 0
        assert len(manager._templates) > 0  # 应该有默认模板
    
    def test_default_templates(self):
        """测试默认模板"""
        manager = NotificationManager()
        
        assert "startup" in manager._templates
        assert "startup_with_error" in manager._templates
        assert "shutdown" in manager._templates
    
    def test_register_template(self):
        """测试注册模板"""
        manager = NotificationManager()
        
        template = "自定义模板: {name}"
        manager.register_template("custom", template)
        
        assert "custom" in manager._templates
        assert manager._templates["custom"] == template
    
    def test_get_template(self):
        """测试获取模板"""
        manager = NotificationManager()
        
        template = manager.get_template("startup")
        assert template is not None
        assert "{module_name}" in template
    
    def test_get_nonexistent_template(self):
        """测试获取不存在的模板"""
        manager = NotificationManager()
        
        template = manager.get_template("nonexistent")
        assert template is None
    
    def test_render_template(self):
        """测试渲染模板"""
        manager = NotificationManager()
        
        content = manager.render_template(
            "startup",
            module_name="测试模块",
            startup_time="2026-03-15 12:00:00",
            service_info="服务信息",
            quick_start="快速开始",
            tips="提示信息"
        )
        
        assert content is not None
        assert "测试模块" in content
        assert "2026-03-15 12:00:00" in content
        assert "服务信息" in content
        assert "快速开始" in content
        assert "提示信息" in content
    
    def test_render_template_missing_variable(self):
        """测试渲染模板缺少变量"""
        manager = NotificationManager()
        
        # 缺少变量会导致错误
        content = manager.render_template(
            "startup",
            module_name="测试模块"
            # 缺少其他必需变量
        )
        
        # 应该返回 None（因为缺少变量）
        assert content is None
    
    def test_register_notification_handler(self):
        """测试注册通知处理器"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("custom", handler)
        
        assert "custom" in manager._notification_handlers
        assert manager._notification_handlers["custom"] == handler
    
    def test_unregister_notification_handler(self):
        """测试注销通知处理器"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("custom", handler)
        manager.unregister_notification_handler("custom")
        
        assert "custom" not in manager._notification_handlers
    
    def test_send_notification_no_handler(self):
        """测试发送通知（无处理器）"""
        manager = NotificationManager()
        
        result = asyncio.run(manager.send_notification("nonexistent", {"content": "测试"}))
        
        assert result is False
    
    def test_send_notification_with_handler(self):
        """测试发送通知（有处理器）"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("test", handler)
        
        result = asyncio.run(manager.send_notification("test", {"content": "测试"}))
        
        assert result is True
    
    def test_send_startup_notification_success(self):
        """测试发送启动通知（成功）"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("startup", handler)
        
        result = asyncio.run(manager.send_startup_notification(
            module_name="测试模块",
            service_info="服务信息",
            quick_start="快速开始",
            tips="提示信息"
        ))
        
        assert result is True
    
    def test_send_startup_notification_with_error(self):
        """测试发送启动通知（有错误）"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("startup", handler)
        
        result = asyncio.run(manager.send_startup_notification(
            module_name="测试模块",
            service_info="服务信息",
            tips="提示信息",
            error_message="错误信息",
            available_commands="可用命令"
        ))
        
        assert result is True
    
    def test_send_shutdown_notification(self):
        """测试发送停止通知"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("shutdown", handler)
        
        result = asyncio.run(manager.send_shutdown_notification(
            module_name="测试模块",
            service_info="服务信息",
            restart_command="python3 -m src.bot"
        ))
        
        assert result is True
    
    def test_send_custom_notification(self):
        """测试发送自定义通知"""
        manager = NotificationManager()
        
        def handler(data):
            return True
        
        manager.register_notification_handler("custom", handler)
        
        result = asyncio.run(manager.send_custom_notification(
            event_type="custom",
            content="自定义通知内容",
            metadata_key="metadata_value"
        ))
        
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])