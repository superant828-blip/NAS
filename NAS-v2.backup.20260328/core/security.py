"""
安全验证模块 - 输入验证、XSS防护、密码强度验证
"""
import re
import html
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    message: str = ""


class InputValidator:
    """输入验证器"""
    
    # 危险字符模式（用于XSS防护）
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>',
    ]
    
    # 文件名不允许的字符
    INVALID_FILENAME_CHARS = r'[<>:"|?*\x00-\x1f]'
    
    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\.[/\\]',
        r'^/etc/',
        r'^/proc/',
        r'^/sys/',
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 255) -> str:
        """清理字符串 - 移除XSS风险"""
        if not value:
            return ""
        
        # HTML转义
        result = html.escape(value)
        
        # 移除换行符和多余空格
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result[:max_length]
    
    @classmethod
    def validate_filename(cls, filename: str) -> ValidationResult:
        """验证文件名"""
        if not filename:
            return ValidationResult(False, "文件名不能为空")
        
        if len(filename) > 255:
            return ValidationResult(False, "文件名过长")
        
        # 检查非法字符
        if re.search(cls.INVALID_FILENAME_CHARS, filename):
            return ValidationResult(False, "文件名包含非法字符")
        
        # 检查路径遍历
        if re.search(r'\.\.[/\\]', filename):
            return ValidationResult(False, "无效的文件名")
        
        # 检查XSS模式
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                return ValidationResult(False, "文件名包含不安全内容")
        
        return ValidationResult(True)
    
    @classmethod
    def validate_email(cls, email: str) -> ValidationResult:
        """验证邮箱格式"""
        if not email:
            return ValidationResult(False, "邮箱不能为空")
        
        # 标准邮箱格式
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return ValidationResult(False, "邮箱格式不正确")
        
        if len(email) > 255:
            return ValidationResult(False, "邮箱过长")
        
        return ValidationResult(True)
    
    @classmethod
    def validate_username(cls, username: str) -> ValidationResult:
        """验证用户名"""
        if not username:
            return ValidationResult(False, "用户名不能为空")
        
        if len(username) < 3:
            return ValidationResult(False, "用户名至少3个字符")
        
        if len(username) > 50:
            return ValidationResult(False, "用户名过长")
        
        # 允许字母、数字、下划线、连字符
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return ValidationResult(False, "用户名只能包含字母、数字、下划线和连字符")
        
        return ValidationResult(True)
    
    @classmethod
    def validate_password_strength(cls, password: str) -> ValidationResult:
        """验证密码强度"""
        if not password:
            return ValidationResult(False, "密码不能为空")
        
        errors = []
        
        if len(password) < 8:
            errors.append("至少8个字符")
        if len(password) > 128:
            errors.append("密码过长")
        if not re.search(r'[a-z]', password):
            errors.append("需要小写字母")
        if not re.search(r'[A-Z]', password):
            errors.append("需要大写字母")
        if not re.search(r'\d', password):
            errors.append("需要数字")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("需要特殊字符")
        
        if errors:
            return ValidationResult(False, f"密码强度不足: {', '.join(errors)}")
        
        return ValidationResult(True)
    
    @classmethod
    def validate_search_query(cls, query: str) -> ValidationResult:
        """验证搜索查询"""
        if not query:
            return ValidationResult(False, "搜索词不能为空")
        
        if len(query) > 100:
            return ValidationResult(False, "搜索词过长")
        
        # 检查SQL注入模式
        sql_patterns = [
            r'(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b)',
            r'(--|;|\/\*|\*\/)',
        ]
        for pattern in sql_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return ValidationResult(False, "搜索词包含不安全内容")
        
        return ValidationResult(True)
    
    @classmethod
    def validate_path(cls, path: str) -> ValidationResult:
        """验证路径安全性"""
        if not path:
            return ValidationResult(False, "路径不能为空")
        
        # 检查路径遍历
        for pattern in cls.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return ValidationResult(False, "路径包含不安全内容")
        
        return ValidationResult(True)
    
    @classmethod
    def sanitize_html(cls, content: str) -> str:
        """HTML内容净化"""
        if not content:
            return ""
        
        # 替换危险标签
        dangerous_tags = ['script', 'iframe', 'object', 'embed', 'link', 'style']
        for tag in dangerous_tags:
            content = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', content, flags=re.IGNORECASE | re.DOTALL)
            content = re.sub(f'<{tag}[^>]*/?>', '', content, flags=re.IGNORECASE)
        
        # 属性净化
        content = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\s+javascript:', '', content, flags=re.IGNORECASE)
        
        return content


# SQL注入防护 - 参数化查询包装
class SQLSanitizer:
    """SQL注入防护"""
    
    @staticmethod
    def escape_like(value: str) -> str:
        """转义LIKE查询的特殊字符"""
        if not value:
            return ""
        # 转义SQL LIKE特殊字符
        return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    
    @staticmethod
    def is_safe_identifier(identifier: str, allowed: List[str]) -> bool:
        """验证标识符是否在允许列表中"""
        return identifier in allowed


# 密码强度检查器
class PasswordStrengthChecker:
    """密码强度检查"""
    
    @staticmethod
    def check(password: str) -> dict:
        """检查密码强度"""
        score = 0
        feedback = []
        
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if len(password) >= 16:
            score += 1
            
        if re.search(r'[a-z]', password):
            score += 1
        if re.search(r'[A-Z]', password):
            score += 1
        if re.search(r'\d', password):
            score += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        
        # 检查常见弱密码
        weak_passwords = [
            'password', '123456', 'qwerty', 'admin', 'letmein',
            'welcome', 'monkey', 'dragon', 'master', 'login'
        ]
        if password.lower() in weak_passwords:
            score = 0
            feedback.append("密码太常见")
        
        # 评级
        if score >= 7:
            level = "strong"
        elif score >= 5:
            level = "medium"
        else:
            level = "weak"
        
        if score < 3:
            feedback.append("密码强度不足")
        
        return {
            "score": score,
            "level": level,
            "feedback": feedback
        }