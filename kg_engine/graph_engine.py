# -*- coding: utf-8 -*-
"""
知识图谱引擎 - 从记忆系统构建知识图谱

融合 Ontology 本体论：
- 类层次结构
- 属性继承
- 关系推理
- 本体查询
"""
import os
import sqlite3
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re

# 导入安全模块
from .security import (
    get_security_manager,
    check_channel_permission,
    sanitize_output,
    PermissionError
)

# 导入本体模块
from .ontology import (
    OntologyManager,
    OntologyClass,
    OntologyProperty,
    get_ontology_manager,
    create_ontology_manager
)


@dataclass
class Entity:
    """实体"""
    id: int
    name: str
    entity_type: str
    importance: float = 0.5
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.entity_type,
            'importance': self.importance,
            'metadata': self.metadata
        }


@dataclass
class Relation:
    """关系"""
    id: int
    from_entity: str
    relation_type: str
    to_entity: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'from': self.from_entity,
            'type': self.relation_type,
            'to': self.to_entity,
            'metadata': self.metadata
        }


@dataclass
class KnowledgeGraph:
    """知识图谱"""
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    query: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            'entities': [e.to_dict() for e in self.entities],
            'relations': [r.to_dict() for r in self.relations],
            'query': self.query,
            'timestamp': self.timestamp,
            'stats': {
                'entity_count': len(self.entities),
                'relation_count': len(self.relations)
            }
        }
    
    def to_mermaid(self, direction: str = "LR") -> str:
        """
        转换为 Mermaid 图表
        
        Args:
            direction: 方向 (LR=左到右, TD=上到下)
            
        Returns:
            str: Mermaid 代码
        """
        lines = [f"graph {direction}"]
        
        # 添加实体（节点）
        for entity in self.entities:
            # 根据类型设置不同形状
            type_emoji = {
                'person': '👤',
                'project': '📋',
                'company': '🏢',
                'system': '💻',
                'technology': '🔧',
                'default': '📌'
            }.get(entity.entity_type, '📌')
            
            safe_name = sanitize_output(entity.name)
            lines.append(f'    {entity.id}["{type_emoji} {safe_name}"]')
        
        # 添加关系（边）
        for relation in self.relations:
            # 关系箭头样式
            arrow = {
                'uses': '-->',
                'depends_on': '-.->',
                'works_at': '---',
                'owns': '-->',
                'default': '-->'
            }.get(relation.relation_type, '-->')
            
            # 添加标签
            label = f'|{relation.relation_type}|'
            
            lines.append(f'    {relation.from_entity} {arrow} {label} {relation.to_entity}')
        
        return '\n'.join(lines)
    
    def to_text(self) -> str:
        """转换为文本描述"""
        lines = ["🕸️ 知识图谱", ""]
        
        # 实体
        lines.append(f"## 实体 ({len(self.entities)} 个)")
        for entity in self.entities:
            safe_name = sanitize_output(entity.name)
            lines.append(f"- {safe_name} ({entity.entity_type})")
        
        # 关系
        lines.append(f"\n## 关系 ({len(self.relations)} 个)")
        for relation in self.relations:
            from_name = sanitize_output(relation.from_entity)
            to_name = sanitize_output(relation.to_entity)
            lines.append(f"- {from_name} --[{relation.relation_type}]--> {to_name}")
        
        return '\n'.join(lines)


class KnowledgeGraphEngine:
    """
    知识图谱引擎
    
    从 MemoryCoreClaw 记忆系统构建知识图谱
    """
    
    def __init__(self, db_path: Optional[str] = None, channel: str = "console",
                 ontology_path: Optional[str] = None):
        """
        初始化图谱引擎
        
        Args:
            db_path: 记忆数据库路径
            channel: 请求渠道（用于权限检查）
            ontology_path: 本体定义文件路径
        """
        # 设置数据库路径
        if db_path is None:
            # 默认路径
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                '.knowledge-graph', 'data', 'memory.db'
            )
        
        self.db_path = db_path
        self.channel = channel
        self.security = get_security_manager()
        
        # 本体管理器（核心增强！）
        self.ontology = create_ontology_manager(ontology_path)
        
        # 缓存
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 300  # 5分钟
    
    def _check_permission(self) -> bool:
        """检查权限"""
        return check_channel_permission(self.channel)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"记忆数据库不存在: {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            if datetime.now().timestamp() - self._cache_time.get(key, 0) < self._cache_ttl:
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any) -> None:
        """设置缓存"""
        self._cache[key] = value
        self._cache_time[key] = datetime.now().timestamp()
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._cache_time.clear()
    
    def get_entities(
        self,
        limit: int = 100,
        entity_type: Optional[str] = None,
        min_importance: float = 0.0
    ) -> List[Entity]:
        """
        获取实体列表
        
        Args:
            limit: 返回数量限制
            entity_type: 实体类型过滤
            min_importance: 最小重要性
            
        Returns:
            list: 实体列表
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        cache_key = f"entities_{limit}_{entity_type}_{min_importance}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 查询实体（从 entities 表或 facts 表）
            query = """
                SELECT id, name, type, importance
                FROM entities
                WHERE importance >= ?
            """
            params = [min_importance]
            
            if entity_type:
                query += " AND type = ?"
                params.append(entity_type)
            
            query += " ORDER BY importance DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            entities = [
                Entity(
                    id=row['id'],
                    name=row['name'],
                    entity_type=row['type'] or 'default',
                    importance=row['importance'] or 0.5
                )
                for row in rows
            ]
            
            # 如果 entities 表为空，从 facts 表补充
            if not entities:
                entities = self._get_entities_from_facts(cursor, limit)
            
            self._set_cache(cache_key, entities)
            return entities
            
        finally:
            conn.close()
    
    def _get_entities_from_facts(self, cursor, limit: int) -> List[Entity]:
        """从 facts 表提取实体"""
        cursor.execute("""
            SELECT id, content, category, importance
            FROM facts
            WHERE category IN ('fact', 'milestone', 'preference')
            ORDER BY importance DESC
            LIMIT ?
        """, [limit])
        
        entities = []
        for i, row in enumerate(cursor.fetchall()):
            # 简单提取：将事实内容作为实体名
            content = row['content']
            if len(content) > 50:
                content = content[:50] + "..."
            
            entities.append(Entity(
                id=row['id'],
                name=content,
                entity_type=row['category'] or 'fact',
                importance=row['importance'] or 0.5
            ))
        
        return entities
    
    def get_relations(
        self,
        entity: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Relation]:
        """
        获取关系列表
        
        Args:
            entity: 实体名称过滤
            relation_type: 关系类型过滤
            limit: 返回数量限制
            
        Returns:
            list: 关系列表
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        cache_key = f"relations_{entity}_{relation_type}_{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 查询关系
            query = "SELECT id, from_entity, relation_type, to_entity FROM relations WHERE 1=1"
            params = []
            
            if entity:
                query += " AND (from_entity LIKE ? OR to_entity LIKE ?)"
                params.extend([f'%{entity}%', f'%{entity}%'])
            
            if relation_type:
                query += " AND relation_type = ?"
                params.append(relation_type)
            
            query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            relations = [
                Relation(
                    id=row['id'],
                    from_entity=row['from_entity'],
                    relation_type=row['relation_type'] or 'related',
                    to_entity=row['to_entity']
                )
                for row in rows
            ]
            
            self._set_cache(cache_key, relations)
            return relations
            
        finally:
            conn.close()
    
    def build_graph(
        self,
        query: Optional[str] = None,
        max_entities: int = 50,
        max_relations: int = 100
    ) -> KnowledgeGraph:
        """
        构建知识图谱
        
        Args:
            query: 查询关键词
            max_entities: 最大实体数
            max_relations: 最大关系数
            
        Returns:
            KnowledgeGraph: 知识图谱对象
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        # 查询缓存
        cache_key = f"graph_{query}_{max_entities}_{max_relations}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        # 获取实体和关系
        entities = self.get_entities(limit=max_entities)
        relations = self.get_relations(limit=max_relations)
        
        # 如果有查询关键词，过滤结果
        if query:
            query_lower = query.lower()
            
            # 过滤实体
            entities = [
                e for e in entities
                if query_lower in e.name.lower() or query_lower in e.entity_type.lower()
            ]
            
            # 过滤关系
            relations = [
                r for r in relations
                if query_lower in r.from_entity.lower()
                or query_lower in r.to_entity.lower()
                or query_lower in r.relation_type.lower()
            ]
        
        # 构建图谱
        graph = KnowledgeGraph(
            entities=entities,
            relations=relations,
            query=query or ""
        )
        
        # ========== 本体推理增强 ==========
        # 基于本体规则，推理额外关系
        for entity in entities:
            # 将关系转换为字典格式
            entity_relations = [
                {'from': r.from_entity, 'type': r.relation_type, 'to': r.to_entity}
                for r in relations
                if r.from_entity == entity.name or r.to_entity == entity.name
            ]
            
            # 使用本体推理额外关系
            inferred = self.ontology.infer_relations(entity.name, entity_relations)
            
            # 添加推理关系到图谱
            for inf in inferred:
                # 检查是否已存在
                exists = any(
                    r.from_entity == inf['from'] and 
                    r.relation_type == inf['type'] and 
                    r.to_entity == inf['to']
                    for r in graph.relations
                )
                if not exists:
                    graph.relations.append(Relation(
                        id=-len(graph.relations) - 1,
                        from_entity=inf['from'],
                        relation_type=inf['type'],
                        to_entity=inf['to'],
                        metadata={'inferred': True, 'rule': inf.get('rule', '')}
                    ))
        
        self._set_cache(cache_key, graph)
        return graph
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        自然语言查询
        
        Args:
            question: 问题
            
        Returns:
            dict: 查询结果
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        # 解析问题
        query = self._parse_question(question)
        
        # 构建图谱
        graph = self.build_graph(query=query)
        
        # 转换为安全结果
        result = graph.to_dict()
        
        # 添加查询分析
        result['analysis'] = {
            'original_question': question,
            'parsed_query': query,
            'entities_found': len(graph.entities),
            'relations_found': len(graph.relations)
        }
        
        # 安全过滤
        return self.security.sanitize_result(result)
    
    def _parse_question(self, question: str) -> str:
        """
        解析问题提取查询关键词
        
        Args:
            question: 用户问题
            
        Returns:
            str: 查询关键词
        """
        # 移除常见问题词
        stop_words = ['涉及', '哪些', '什么', '关系', '关联', '和', '与', '的', '是']
        
        query = question
        for word in stop_words:
            query = query.replace(word, ' ')
        
        return query.strip()
    
    def to_mermaid(self, query: Optional[str] = None) -> str:
        """
        生成 Mermaid 图表
        
        Args:
            query: 查询关键词
            
        Returns:
            str: Mermaid 代码
        """
        graph = self.build_graph(query=query)
        return graph.to_mermaid()
    
    def to_text(self, query: Optional[str] = None) -> str:
        """
        生成文本描述
        
        Args:
            query: 查询关键词
            
        Returns:
            str: 文本描述
        """
        graph = self.build_graph(query=query)
        return graph.to_text()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息
        
        Returns:
            dict: 统计信息
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # 实体数量
            cursor.execute("SELECT COUNT(*) as count FROM entities")
            stats['entity_count'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM facts")
            stats['fact_count'] = cursor.fetchone()['count']
            
            # 关系数量
            cursor.execute("SELECT COUNT(*) as count FROM relations")
            stats['relation_count'] = cursor.fetchone()['count']
            
            # 实体类型分布
            cursor.execute("""
                SELECT type, COUNT(*) as count 
                FROM entities 
                GROUP BY type
            """)
            stats['entity_types'] = {
                row['type']: row['count'] 
                for row in cursor.fetchall()
            }
            
            # 关系类型分布
            cursor.execute("""
                SELECT relation_type, COUNT(*) as count 
                FROM relations 
                GROUP BY relation_type
            """)
            stats['relation_types'] = {
                row['relation_type']: row['count'] 
                for row in cursor.fetchall()
            }
            
            return self.security.sanitize_result(stats)
            
        finally:
            conn.close()
    
    def discover_related(
        self,
        entity: str,
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        发现相关实体（给定实体的一度或二度关联）
        
        Args:
            entity: 实体名称
            depth: 深度（1=一度关联，2=二度关联）
            
        Returns:
            dict: 相关实体信息
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        graph = self.build_graph(query=entity)
        
        # 找到直接关联的实体
        related = {
            'directly_related': [],
            'relation_types': set()
        }
        
        for relation in graph.relations:
            if entity.lower() in relation.from_entity.lower():
                related['directly_related'].append({
                    'entity': relation.to_entity,
                    'relation': relation.relation_type
                })
                related['relation_types'].add(relation.relation_type)
            elif entity.lower() in relation.to_entity.lower():
                related['directly_related'].append({
                    'entity': relation.from_entity,
                    'relation': relation.relation_type
                })
                related['relation_types'].add(relation.relation_type)
        
        # 转换为列表
        related['relation_types'] = list(related['relation_types'])
        
        result = {
            'query_entity': entity,
            'depth': depth,
            'directly_related': related['directly_related'],
            'relation_types': related['relation_types'],
            'total_related': len(related['directly_related'])
        }
        
        return self.security.sanitize_result(result)
    
    # ========== Ontology 本体增强方法 ==========
    
    def semantic_query(self, question: str) -> Dict[str, Any]:
        """
        基于本体的语义查询
        
        与普通 query 的区别：
        - 理解实体类型（Person, Project, Technology 等）
        - 理解关系语义（不只是关键词匹配）
        - 利用本体推理补全结果
        
        Args:
            question: 自然语言问题
            
        Returns:
            dict: 语义查询结果
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        # 1. 解析问题，提取关键实体和意图
        parsed = self._parse_semantic_question(question)
        
        # 2. 利用本体理解实体类型
        entity_type = self._infer_entity_type(parsed['entity'])
        
        # 3. 利用本体规范化关系
        normalized_rels = [
            self.ontology.normalize_relation_type(r)
            for r in parsed.get('relations', [])
        ]
        
        # 4. 构建图谱
        graph = self.build_graph(query=parsed['entity'])
        
        # 5. 利用本体推理补全
        # 获取所有关系用于推理
        all_relations = [
            {'from': r.from_entity, 'type': r.relation_type, 'to': r.to_entity}
            for r in graph.relations
        ]
        
        # 本体推理
        inferred_relations = self.ontology.infer_relations(
            parsed['entity'], 
            all_relations
        )
        
        # 6. 构建结果
        result = {
            'question': question,
            'parsed': parsed,
            'entity_type': entity_type,
            'normalized_relations': normalized_rels,
            'inferred_relations': inferred_relations,
            'graph': graph.to_dict()
        }
        
        return self.security.sanitize_result(result)
    
    def _parse_semantic_question(self, question: str) -> Dict[str, Any]:
        """
        解析语义问题
        
        Args:
            question: 原始问题
            
        Returns:
            dict: 解析结果
        """
        # 移除常见问题词
        stop_words = ['涉及', '哪些', '什么', '关系', '关联', '和', '与', '的', 
                     '是谁', '是什么', '用', '使用', '掌握', '负责', '参与']
        
        query = question
        for word in stop_words:
            query = query.replace(word, ' ')
        
        # 提取实体
        entity = query.strip()
        
        # 提取关系
        relations = []
        for word in ['使用', '掌握', '负责', '参与', '依赖', '关联']:
            if word in question:
                relations.append(word)
        
        return {
            'entity': entity,
            'relations': relations,
            'original': question
        }
    
    def _infer_entity_type(self, entity: str) -> Optional[str]:
        """
        推断实体类型（基于本体）
        
        Args:
            entity: 实体名
            
        Returns:
            str: 实体类型
        """
        # 构建图谱
        graph = self.build_graph(query=entity)
        
        # 找到匹配的实体
        for entity_obj in graph.entities:
            if entity.lower() in entity_obj.name.lower():
                # 尝试映射到本体类
                return self._map_to_ontology_class(entity_obj.entity_type)
        
        return None
    
    def _map_to_ontology_class(self, type_str: str) -> str:
        """
        将记忆系统类型映射到本体类
        
        Args:
            type_str: 记忆系统类型
            
        Returns:
            str: 本体类名
        """
        mapping = {
            'person': 'Person',
            'user': 'Person',
            'agent': 'Person',
            'project': 'Project',
            'milestone': 'Project',
            'technology': 'Technology',
            'skill': 'Technology',
            'tool': 'Technology',
            'system': 'System',
            'company': 'Organization',
            'organization': 'Organization',
            'knowledge': 'Knowledge',
            'fact': 'Knowledge',
            'lesson': 'Knowledge',
            'decision': 'Decision',
            'event': 'Event'
        }
        
        type_lower = type_str.lower()
        return mapping.get(type_lower, 'Entity')
    
    def get_ontology_schema(self) -> Dict[str, Any]:
        """
        获取本体模式（类层次结构）
        
        Returns:
            dict: 本体模式
        """
        # 权限检查
        if not self._check_permission():
            raise PermissionError("权限不足，无法访问知识图谱")
        
        schema = {
            'classes': {},
            'properties': {}
        }
        
        # 获取所有类
        for name, cls in self.ontology.classes.items():
            schema['classes'][name] = {
                'label': cls.label,
                'description': cls.description,
                'parent': cls.parent,
                'properties': list(cls.properties.keys())
            }
        
        # 获取所有属性
        for name, prop in self.ontology.properties.items():
            schema['properties'][name] = {
                'label': prop.label,
                'domain': prop.domain,
                'range': prop.range,
                'description': prop.description
            }
        
        return self.security.sanitize_result(schema)
    
    def query_ontology(self, query: str) -> Dict[str, Any]:
        """
        直接查询本体
        
        Args:
            query: 查询内容
            
        Returns:
            dict: 本体查询结果
        """
        return self.ontology.query_ontology(query)


def create_graph_engine(
    db_path: Optional[str] = None,
    channel: str = "console",
    ontology_path: Optional[str] = None
) -> KnowledgeGraphEngine:
    """
    创建图谱引擎实例（工厂函数）
    
    Args:
        db_path: 数据库路径
        channel: 渠道
        ontology_path: 本体定义文件路径
        
    Returns:
        KnowledgeGraphEngine: 图谱引擎
    """
    return KnowledgeGraphEngine(
        db_path=db_path, 
        channel=channel,
        ontology_path=ontology_path
    )