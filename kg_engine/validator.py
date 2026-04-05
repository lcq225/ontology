# -*- coding: utf-8 -*-
"""
Ontology Validator - 本体约束验证引擎

功能：
- 类型验证
- 属性验证（必填/可选/枚举）
- 关系验证（类型/基数/环检测）
- 自定义规则验证
- 敏感信息检测

版本：v2.0
日期：2026-03-29
"""

import re
import sys
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
except ImportError:
    print("⚠️ 请安装 PyYAML: pip install pyyaml")
    sys.exit(1)


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    
    def merge(self, other: 'ValidationResult'):
        """合并验证结果"""
        self.valid = self.valid and other.valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)
        return self
    
    def __bool__(self):
        return self.valid
    
    def __str__(self):
        status = "✅ 通过" if self.valid else "❌ 失败"
        lines = [f"验证结果：{status}"]
        
        if self.errors:
            lines.append(f"\n错误 ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  ❌ {error}")
        
        if self.warnings:
            lines.append(f"\n警告 ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠️ {warning}")
        
        if self.info:
            lines.append(f"\n信息 ({len(self.info)}):")
            for info in self.info:
                lines.append(f"  ℹ️ {info}")
        
        return "\n".join(lines)


class OntologyValidator:
    """本体约束验证器"""
    
    def __init__(self, schema_path: str):
        """
        初始化验证器
        
        Args:
            schema_path: Schema YAML 文件路径
        """
        self.schema_path = Path(schema_path)
        self.schema = self._load_schema()
        self._cache = {}
    
    def _load_schema(self) -> Dict:
        """加载 Schema 定义"""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            schema = yaml.safe_load(f)
        
        # 验证 Schema 结构
        self._validate_schema_structure(schema)
        
        return schema
    
    def _validate_schema_structure(self, schema: Dict):
        """验证 Schema 本身的结构"""
        required_sections = ['types', 'relations', 'forbidden_properties']
        
        for section in required_sections:
            if section not in schema:
                raise ValueError(f"Schema missing required section: {section}")
        
        if 'version' not in schema:
            print("⚠️ Schema 未指定版本号")
    
    def validate_entity(self, entity_type: str, properties: Dict, entity_id: str = None) -> ValidationResult:
        """
        验证实体
        
        Args:
            entity_type: 实体类型（如 Person, Task, Project）
            properties: 实体属性字典
            entity_id: 实体 ID（可选，用于错误信息）
        
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(True, [], [], [])
        entity_ref = f"{entity_type}({entity_id})" if entity_id else entity_type
        
        # 1. 检查类型是否存在
        if entity_type not in self.schema['types']:
            # 检查是否有父类型
            base_type = self._find_base_type(entity_type)
            if not base_type:
                result.errors.append(f"未知实体类型：{entity_type}")
                result.valid = False
                return result
            # 使用父类型验证
            type_def = self.schema['types'][base_type]
        else:
            type_def = self.schema['types'][entity_type]
        
        # 2. 检查必填字段
        required_fields = type_def.get('required', [])
        for field_name in required_fields:
            if field_name not in properties:
                result.errors.append(f"[{entity_ref}] 缺少必填字段：{field_name}")
                result.valid = False
        
        # 3. 检查枚举值
        enums = type_def.get('enums', {})
        for field_name, allowed_values in enums.items():
            if field_name in properties:
                value = properties[field_name]
                if value not in allowed_values:
                    result.errors.append(
                        f"[{entity_ref}] 字段 '{field_name}' 的值 '{value}' 不在允许范围内: {allowed_values}"
                    )
                    result.valid = False
        
        # 4. 检查禁止属性（敏感信息）
        forbidden = self.schema.get('forbidden_properties', [])
        for prop in forbidden:
            if prop in properties:
                result.errors.append(f"[{entity_ref}] 禁止存储敏感属性：{prop}")
                result.valid = False
        
        # 5. 执行自定义验证规则
        validations = type_def.get('validations', [])
        for rule in validations:
            validation_result = self._evaluate_rule(rule, properties, entity_ref)
            if not validation_result.valid:
                result.merge(validation_result)
        
        # 6. 检查字段类型
        type_checks = self._check_field_types(properties, type_def, entity_ref)
        result.merge(type_checks)
        
        # 7. 应用默认值检查（仅警告）
        defaults = self.schema.get('defaults', {}).get(entity_type, {})
        for field_name, default_value in defaults.items():
            if field_name not in properties:
                result.warnings.append(f"[{entity_ref}] 字段 '{field_name}' 未设置，将使用默认值：{default_value}")
        
        return result
    
    def validate_relation(self, from_type: str, relation_type: str, to_type: str, 
                         from_id: str = None, to_id: str = None) -> ValidationResult:
        """
        验证关系
        
        Args:
            from_type: 源实体类型
            relation_type: 关系类型
            to_type: 目标实体类型
            from_id: 源实体 ID（可选）
            to_id: 目标实体 ID（可选）
        
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(True, [], [], [])
        relation_ref = f"{relation_type}({from_id} -> {to_id})" if from_id and to_id else relation_type
        
        # 1. 检查关系类型是否存在
        if relation_type not in self.schema['relations']:
            result.errors.append(f"未知关系类型：{relation_type}")
            result.valid = False
            return result
        
        rel_def = self.schema['relations'][relation_type]
        
        # 2. 检查 from_types 约束
        from_types = rel_def.get('from_types', [])
        if from_type not in from_types:
            # 检查是否是子类型
            if not self._is_subtype_of(from_type, from_types):
                result.errors.append(
                    f"[{relation_ref}] 源类型 '{from_type}' 不允许，允许的类型：{from_types}"
                )
                result.valid = False
        
        # 3. 检查 to_types 约束
        to_types = rel_def.get('to_types', [])
        if to_type not in to_types:
            if not self._is_subtype_of(to_type, to_types):
                result.errors.append(
                    f"[{relation_ref}] 目标类型 '{to_type}' 不允许，允许的类型：{to_types}"
                )
                result.valid = False
        
        # 4. 检查环（如果关系标记为 acyclic）
        if rel_def.get('acyclic', False):
            # 这里需要图结构来检测环，简化处理：检查自环
            if from_id and to_id and from_id == to_id:
                result.errors.append(f"[{relation_ref}] 禁止自环（acyclic 关系）")
                result.valid = False
        
        # 5. 检查对称关系的反向
        if rel_def.get('symmetric', False):
            result.info.append(f"对称关系：将自动创建反向关系 {to_type} -[{relation_type}]-> {from_type}")
        
        return result
    
    def validate_batch(self, entities: List[Dict], relations: List[Dict]) -> ValidationResult:
        """
        批量验证实体和关系
        
        Args:
            entities: 实体列表 [{"id": str, "type": str, "properties": dict}]
            relations: 关系列表 [{"from_id": str, "relation_type": str, "to_id": str}]
        
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(True, [], [], [])
        
        # 1. 验证所有实体
        entity_map = {}
        for entity in entities:
            entity_id = entity.get('id')
            entity_type = entity.get('type')
            properties = entity.get('properties', {})
            
            validation = self.validate_entity(entity_type, properties, entity_id)
            result.merge(validation)
            
            if entity_id:
                entity_map[entity_id] = entity
        
        # 2. 验证所有关系
        for relation in relations:
            from_id = relation.get('from_id')
            to_id = relation.get('to_id')
            relation_type = relation.get('relation_type')
            
            # 获取实体类型
            from_entity = entity_map.get(from_id)
            to_entity = entity_map.get(to_id)
            
            if not from_entity:
                result.errors.append(f"关系源实体不存在：{from_id}")
                result.valid = False
                continue
            
            if not to_entity:
                result.errors.append(f"关系目标实体不存在：{to_id}")
                result.valid = False
                continue
            
            validation = self.validate_relation(
                from_entity['type'],
                relation_type,
                to_entity['type'],
                from_id,
                to_id
            )
            result.merge(validation)
        
        return result
    
    def _find_base_type(self, entity_type: str) -> Optional[str]:
        """查找父类型（支持继承）"""
        for type_name, type_def in self.schema['types'].items():
            if type_def.get('parent') == entity_type:
                return type_name
        return None
    
    def _is_subtype_of(self, entity_type: str, parent_types: List[str]) -> bool:
        """检查是否是某类型的子类型"""
        if entity_type in parent_types:
            return True
        
        # 递归检查父类型
        type_def = self.schema['types'].get(entity_type, {})
        parent = type_def.get('parent')
        
        if parent:
            return self._is_subtype_of(parent, parent_types)
        
        return False
    
    def _evaluate_rule(self, rule: str, properties: Dict, entity_ref: str) -> ValidationResult:
        """
        评估自定义验证规则
        
        支持的规则格式：
        - "field must be non-empty string"
        - "email must be valid email format if exists"
        - "end >= start if both exist"
        - "field must be between X and Y"
        """
        result = ValidationResult(True, [], [], [])
        
        # 规则 1: 非空字符串检查
        if "must be non-empty string" in rule:
            field_name = rule.split(" must be")[0]
            if field_name in properties:
                value = properties[field_name]
                if not isinstance(value, str) or not value.strip():
                    result.errors.append(f"[{entity_ref}] 字段 '{field_name}' 必须是非空字符串")
                    result.valid = False
        
        # 规则 2: 邮箱格式检查
        elif "must be valid email format" in rule:
            field_name = rule.split(" must be")[0]
            if field_name in properties:
                value = properties[field_name]
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, value):
                    result.errors.append(f"[{entity_ref}] 字段 '{field_name}' 不是有效的邮箱格式")
                    result.valid = False
        
        # 规则 3: 日期比较检查
        elif ">=" in rule and "if" in rule:
            # 解析规则："end >= start if both exist"
            match = re.match(r'(\w+)\s*>=\s*(\w+)\s+if\s+(.+)', rule)
            if match:
                field1, field2, condition = match.groups()
                
                if condition == "both exist":
                    if field1 in properties and field2 in properties:
                        try:
                            val1 = self._parse_date(properties[field1])
                            val2 = self._parse_date(properties[field2])
                            if val1 < val2:
                                result.errors.append(
                                    f"[{entity_ref}] 字段 '{field1}' ({val1}) 必须 >= '{field2}' ({val2})"
                                )
                                result.valid = False
                        except (ValueError, TypeError) as e:
                            result.warnings.append(f"[{entity_ref}] 无法解析日期：{e}")
                
                elif condition == "exists":
                    if field1 in properties and field2 in properties:
                        try:
                            val1 = self._parse_date(properties[field1])
                            val2 = self._parse_date(properties[field2])
                            if val1 < val2:
                                result.errors.append(
                                    f"[{entity_ref}] 字段 '{field1}' 必须 >= '{field2}'"
                                )
                                result.valid = False
                        except (ValueError, TypeError) as e:
                            result.warnings.append(f"[{entity_ref}] 无法解析日期：{e}")
        
        # 规则 4: 范围检查
        elif "must be between" in rule:
            match = re.match(r'(\w+)\s+must be between\s+([\d.]+)\s+and\s+([\d.]+)', rule)
            if match:
                field_name, min_val, max_val = match.groups()
                if field_name in properties:
                    value = properties[field_name]
                    try:
                        num_value = float(value)
                        if not (float(min_val) <= num_value <= float(max_val)):
                            result.errors.append(
                                f"[{entity_ref}] 字段 '{field_name}' 的值 {value} 必须在 {min_val} 和 {max_val} 之间"
                            )
                            result.valid = False
                    except (ValueError, TypeError):
                        result.errors.append(f"[{entity_ref}] 字段 '{field_name}' 必须是数字")
                        result.valid = False
        
        # 规则 5: 存在性检查
        elif "must exist" in rule:
            field_name = rule.split(" must exist")[0]
            if field_name not in properties:
                result.errors.append(f"[{entity_ref}] 字段 '{field_name}' 必须存在")
                result.valid = False
        
        return result
    
    def _parse_date(self, value: Any) -> datetime:
        """解析日期字符串"""
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            # 尝试多种格式
            formats = [
                '%Y-%m-%d',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%SZ',
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        
        raise ValueError(f"无法解析日期：{value}")
    
    def _check_field_types(self, properties: Dict, type_def: Dict, entity_ref: str) -> ValidationResult:
        """检查字段类型"""
        result = ValidationResult(True, [], [], [])
        
        # 简单类型检查
        for field_name, value in properties.items():
            # 检查列表类型
            if isinstance(value, list):
                if not value:
                    continue
                # 检查列表元素类型是否一致
                first_type = type(value[0])
                for item in value[1:]:
                    if type(item) != first_type:
                        result.warnings.append(
                            f"[{entity_ref}] 字段 '{field_name}' 的列表元素类型不一致"
                        )
                        break
        
        return result
    
    def get_schema_info(self) -> Dict:
        """获取 Schema 信息"""
        return {
            'version': self.schema.get('version', 'unknown'),
            'updated': self.schema.get('updated', 'unknown'),
            'entity_types': len(self.schema['types']),
            'relation_types': len(self.schema['relations']),
            'forbidden_properties': len(self.schema.get('forbidden_properties', [])),
            'inference_rules': len(self.schema.get('inference_rules', [])),
        }


# ==================== 便捷函数 ====================

def create_validator(schema_path: str = None) -> OntologyValidator:
    """
    创建验证器实例
    
    Args:
        schema_path: Schema 文件路径（可选，默认使用内置路径）
    
    Returns:
        OntologyValidator: 验证器实例
    """
    if schema_path is None:
        # 默认路径
        schema_path = Path(__file__).parent.parent / 'schema' / 'ontology_schema.yaml'
    
    return OntologyValidator(str(schema_path))


def quick_validate(entity_type: str, properties: Dict) -> ValidationResult:
    """
    快速验证（使用默认 Schema）
    
    Args:
        entity_type: 实体类型
        properties: 属性字典
    
    Returns:
        ValidationResult: 验证结果
    """
    validator = create_validator()
    return validator.validate_entity(entity_type, properties)


# ==================== 主函数（CLI 测试） ====================

if __name__ == '__main__':
    # 测试验证器
    print("=" * 60)
    print("Ontology Validator 测试")
    print("=" * 60)
    
    # 创建验证器
    schema_path = Path(__file__).parent.parent / 'schema' / 'ontology_schema.yaml'
    validator = OntologyValidator(str(schema_path))
    
    # 获取 Schema 信息
    info = validator.get_schema_info()
    print(f"\nSchema 版本：{info['version']}")
    print(f"更新时间：{info['updated']}")
    print(f"实体类型：{info['entity_types']}")
    print(f"关系类型：{info['relation_types']}")
    print(f"禁止属性：{info['forbidden_properties']}")
    print(f"推理规则：{info['inference_rules']}")
    
    # 测试 1: 有效实体
    print("\n" + "=" * 60)
    print("测试 1: 创建有效 Person 实体")
    print("=" * 60)
    result = validator.validate_entity("Person", {
        "name": "Alice",
        "email": "alice@example.com"
    })
    print(result)
    
    # 测试 2: 无效实体（缺少必填字段）
    print("\n" + "=" * 60)
    print("测试 2: 创建无效 Task 实体（缺少 status）")
    print("=" * 60)
    result = validator.validate_entity("Task", {
        "title": "测试任务"
        # 缺少 status
    })
    print(result)
    
    # 测试 3: 枚举值验证
    print("\n" + "=" * 60)
    print("测试 3: Task 枚举值验证")
    print("=" * 60)
    result = validator.validate_entity("Task", {
        "title": "测试任务",
        "status": "invalid_status",  # 无效枚举
        "priority": "high"
    })
    print(result)
    
    # 测试 4: 敏感信息检测
    print("\n" + "=" * 60)
    print("测试 4: 敏感信息检测")
    print("=" * 60)
    result = validator.validate_entity("Account", {
        "service": "github",
        "username": "testuser",
        "password": "secret123"  # 禁止属性
    })
    print(result)
    
    # 测试 5: 关系验证
    print("\n" + "=" * 60)
    print("测试 5: 关系验证")
    print("=" * 60)
    result = validator.validate_relation("Person", "works_at", "Company")
    print(result)
    
    # 测试 6: 无效关系
    print("\n" + "=" * 60)
    print("测试 6: 无效关系（类型不匹配）")
    print("=" * 60)
    result = validator.validate_relation("Person", "owns", "Location")
    print(result)
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
