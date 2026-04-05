# -*- coding: utf-8 -*-
"""
Ontology Security - 安全控制模块

功能：
- 渠道权限检查
- 敏感信息检测
- 数据脱敏
- 访问控制

版本：v2.0
日期：2026-03-29
"""

import re
import sys
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class SecurityResult:
    """安全检查结果"""
    allowed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_data: Any = None
    
    def __bool__(self):
        return self.allowed
    
    def __str__(self):
        status = "✅ 允许" if self.allowed else "❌ 拒绝"
        lines = [f"安全结果：{status}"]
        
        if self.errors:
            lines.append(f"\n错误 ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  ❌ {error}")
        
        if self.warnings:
            lines.append(f"\n警告 ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠️ {warning}")
        
        return "\n".join(lines)


class OntologySecurity:
    """Ontology 安全控制器"""
    
    # 默认允许的用户 ID
    DEFAULT_ALLOWED_USERS = {
        'HI2044',  # User
    }
    
    # 禁止的属性名（敏感信息）
    FORBIDDEN_PROPERTIES = {
        'password',
        'secret',
        'token',
        'api_key',
        'api_secret',
        'credential',
        'credentials',
        'private_key',
        'private_key_pem',
        'access_token',
        'refresh_token',
        'auth_token',
        'session_token',
        'bearer_token',
        'client_secret',
        'database_password',
        'db_password',
        'encryption_key',
        'master_key',
        'signing_key',
        'passwd',
        'pwd',
        'secret_key',
    }
    
    # 敏感信息模式（正则）
    SENSITIVE_PATTERNS = [
        (r'password\s*[=:]\s*\S+', '密码'),
        (r'token\s*[=:]\s*\S+', '令牌'),
        (r'secret\s*[=:]\s*\S+', '密钥'),
        (r'api_key\s*[=:]\s*\S+', 'API 密钥'),
        (r'Bearer\s+\S+', 'Bearer Token'),
        (r'Basic\s+\S+', 'Basic Auth'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '邮箱'),
        (r'\b\d{11}\b', '手机号'),
        (r'\b\d{17}[\dXx]\b', '身份证号'),
    ]
    
    def __init__(self, allowed_users: Set[str] = None, allowed_channels: List[str] = None):
        """
        初始化安全控制器
        
        Args:
            allowed_users: 允许的用户 ID 集合
            allowed_channels: 允许的渠道列表
        """
        self.allowed_users = allowed_users or self.DEFAULT_ALLOWED_USERS.copy()
        self.allowed_channels = allowed_channels or ['console', 'wecom']
    
    def check_channel_permission(self, channel: str, user_id: str = None) -> SecurityResult:
        """
        检查渠道权限
        
        Args:
            channel: 渠道名称（console, wecom, dingtalk 等）
            user_id: 用户 ID（可选）
        
        Returns:
            SecurityResult: 权限检查结果
        """
        errors = []
        warnings = []
        
        # 1. 本地控制台完全信任
        if channel == 'console':
            return SecurityResult(True, [], [], None)
        
        # 2. 检查渠道是否在允许列表中
        channel_allowed = False
        for allowed_channel in self.allowed_channels:
            if channel.startswith(allowed_channel):
                channel_allowed = True
                break
        
        if not channel_allowed:
            errors.append(f"未授权的渠道：{channel}")
            return SecurityResult(False, errors, warnings, None)
        
        # 3. 如果提供了 user_id，检查是否在允许用户列表中
        if user_id:
            if user_id not in self.allowed_users:
                errors.append(f"未授权的用户：{user_id}")
                return SecurityResult(False, errors, warnings, None)
        
        return SecurityResult(True, [], [], None)
    
    def validate_properties(self, properties: Dict, strict: bool = True) -> SecurityResult:
        """
        验证属性（检测敏感信息）
        
        Args:
            properties: 属性字典
            strict: 严格模式（True=拒绝，False=警告）
        
        Returns:
            SecurityResult: 验证结果
        """
        errors = []
        warnings = []
        
        # 1. 检查禁止的属性名
        for prop in properties.keys():
            prop_lower = prop.lower()
            if prop_lower in self.FORBIDDEN_PROPERTIES:
                if strict:
                    errors.append(f"禁止存储敏感属性：{prop}")
                else:
                    warnings.append(f"警告：存储敏感属性：{prop}")
        
        # 2. 检查属性值是否包含敏感信息
        for prop_name, prop_value in properties.items():
            if isinstance(prop_value, str):
                for pattern, description in self.SENSITIVE_PATTERNS:
                    if re.search(pattern, prop_value, re.IGNORECASE):
                        warnings.append(f"字段 '{prop_name}' 可能包含敏感信息（{description}）")
            
            # 递归检查嵌套字典
            elif isinstance(prop_value, dict):
                nested_result = self.validate_properties(prop_value, strict)
                errors.extend(nested_result.errors)
                warnings.extend(nested_result.warnings)
        
        allowed = len(errors) == 0
        return SecurityResult(allowed, errors, warnings, None)
    
    def sanitize_output(self, data: Any, level: str = 'normal') -> Any:
        """
        脱敏输出数据
        
        Args:
            data: 原始数据
            level: 脱敏级别（'normal', 'strict'）
        
        Returns:
            Any: 脱敏后的数据
        """
        if isinstance(data, dict):
            return self._sanitize_dict(data, level)
        elif isinstance(data, list):
            return [self.sanitize_output(item, level) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string(data, level)
        else:
            return data
    
    def _sanitize_dict(self, data: Dict, level: str) -> Dict:
        """脱敏字典"""
        sanitized = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # 跳过敏感字段
            if key_lower in self.FORBIDDEN_PROPERTIES:
                sanitized[key] = "***REDACTED***"
                continue
            
            # 递归脱敏
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value, level)
            elif isinstance(value, list):
                sanitized[key] = [self.sanitize_output(item, level) for item in value]
            elif isinstance(value, str):
                sanitized[key] = self._sanitize_string(value, level)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_string(self, text: str, level: str) -> str:
        """脱敏字符串"""
        result = text
        
        # 邮箱脱敏
        email_pattern = r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[A-Z|a-z]{2,})\b'
        result = re.sub(email_pattern, r'\1***@\2', result)
        
        # 手机号脱敏
        phone_pattern = r'\b(\d{3})\d{4}(\d{4})\b'
        result = re.sub(phone_pattern, r'\1****\2', result)
        
        # 身份证号脱敏
        id_pattern = r'\b(\d{6})\d{8}(\d{3}[\dXx])\b'
        result = re.sub(id_pattern, r'\1********\2', result)
        
        # Token 脱敏
        token_pattern = r'\b(token\s*[=:]\s*)(\S+)\b'
        result = re.sub(token_pattern, r'\1***REDACTED***', result, flags=re.IGNORECASE)
        
        # 密码脱敏
        password_pattern = r'\b(password\s*[=:]\s*)(\S+)\b'
        result = re.sub(password_pattern, r'\1***REDACTED***', result, flags=re.IGNORECASE)
        
        return result
    
    def add_allowed_user(self, user_id: str):
        """添加允许的用户"""
        self.allowed_users.add(user_id)
    
    def remove_allowed_user(self, user_id: str):
        """移除允许的用户"""
        self.allowed_users.discard(user_id)
    
    def get_security_report(self) -> Dict:
        """获取安全报告"""
        return {
            'allowed_users': list(self.allowed_users),
            'allowed_channels': self.allowed_channels,
            'forbidden_properties_count': len(self.FORBIDDEN_PROPERTIES),
            'sensitive_patterns_count': len(self.SENSITIVE_PATTERNS),
        }


# ==================== 便捷函数 ====================

def create_security_manager(allowed_users: Set[str] = None) -> OntologySecurity:
    """
    创建安全管理器实例
    
    Args:
        allowed_users: 允许的用户 ID 集合
    
    Returns:
        OntologySecurity: 安全管理器
    """
    return OntologySecurity(allowed_users)


def quick_security_check(channel: str, user_id: str = None) -> SecurityResult:
    """
    快速安全检查
    
    Args:
        channel: 渠道名称
        user_id: 用户 ID
    
    Returns:
        SecurityResult: 检查结果
    """
    security = create_security_manager()
    return security.check_channel_permission(channel, user_id)


def check_sensitive_data(properties: Dict) -> SecurityResult:
    """
    快速检查敏感数据
    
    Args:
        properties: 属性字典
    
    Returns:
        SecurityResult: 检查结果
    """
    security = create_security_manager()
    return security.validate_properties(properties)


def get_security_manager(allowed_users: set = None) -> OntologySecurity:
    """
    获取安全管理器实例（别名，兼容旧代码）
    
    Args:
        allowed_users: 允许的用户 ID 集合
    
    Returns:
        OntologySecurity: 安全管理器
    """
    return create_security_manager(allowed_users)


def check_channel_permission(channel: str, user_id: str = None) -> SecurityResult:
    """
    快速检查渠道权限（便捷函数）
    
    Args:
        channel: 渠道名称
        user_id: 用户 ID
    
    Returns:
        SecurityResult: 检查结果
    """
    security = create_security_manager()
    return security.check_channel_permission(channel, user_id)


def sanitize_output(data: Any, level: str = 'normal') -> Any:
    """
    快速脱敏输出（便捷函数）
    
    Args:
        data: 原始数据
        level: 脱敏级别
    
    Returns:
        Any: 脱敏后的数据
    """
    security = create_security_manager()
    return security.sanitize_output(data, level)


class PermissionError(Exception):
    """权限错误（兼容旧代码）"""
    pass


# ==================== 主函数（CLI 测试） ====================

if __name__ == '__main__':
    print("=" * 60)
    print("Ontology Security 测试")
    print("=" * 60)
    
    # 创建安全管理器
    security = OntologySecurity()
    
    # 获取安全报告
    report = security.get_security_report()
    print(f"\n允许用户：{report['allowed_users']}")
    print(f"允许渠道：{report['allowed_channels']}")
    print(f"禁止属性数：{report['forbidden_properties_count']}")
    print(f"敏感模式数：{report['sensitive_patterns_count']}")
    
    # 测试 1: 渠道权限（console）
    print("\n" + "=" * 60)
    print("测试 1: Console 渠道权限")
    print("=" * 60)
    result = security.check_channel_permission('console', 'any_user')
    print(result)
    
    # 测试 2: 渠道权限（wecom 授权用户）
    print("\n" + "=" * 60)
    print("测试 2: WeCom 授权用户权限")
    print("=" * 60)
    result = security.check_channel_permission('wecom', 'HI2044')
    print(result)
    
    # 测试 3: 渠道权限（wecom 未授权用户）
    print("\n" + "=" * 60)
    print("测试 3: WeCom 未授权用户权限")
    print("=" * 60)
    result = security.check_channel_permission('wecom', 'UNAUTHORIZED')
    print(result)
    
    # 测试 4: 敏感信息检测（密码）
    print("\n" + "=" * 60)
    print("测试 4: 敏感信息检测（密码）")
    print("=" * 60)
    result = security.validate_properties({
        "service": "github",
        "username": "testuser",
        "password": "secret123"
    })
    print(result)
    
    # 测试 5: 敏感信息检测（Token）
    print("\n" + "=" * 60)
    print("测试 5: 敏感信息检测（Token）")
    print("=" * 60)
    result = security.validate_properties({
        "content": "API token: sk-test-token-placeholder"
    })
    print(result)
    
    # 测试 6: 输出脱敏
    print("\n" + "=" * 60)
    print("测试 6: 输出脱敏")
    print("=" * 60)
    data = {
        "name": "Alice",
        "email": "alice@example.com",
        "password": "secret123",
        "phone": "13800138000",
        "description": "Contact: alice@example.com, 13800138000"
    }
    sanitized = security.sanitize_output(data, level='strict')
    print("原始数据:")
    print(data)
    print("\n脱敏后:")
    print(sanitized)
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
