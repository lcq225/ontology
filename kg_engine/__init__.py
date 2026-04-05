# -*- coding: utf-8 -*-
"""
KG Engine - Knowledge Graph Engine

Knowledge Graph System with entity recognition, relation extraction, graph query and visualization

Integration with Ontology:
- Class hierarchy
- Property inheritance
- Relation inference
- Ontology query

Core Features:
- Entity recognition and extraction
- Relation extraction and construction
- Ontology reasoning enhancement
- Knowledge graph query
- Mermaid visualization
- Text description output

Usage Example:
    from kg_engine import create_graph_engine
    
    kg = create_graph_engine()
    result = kg.semantic_query("What technologies does Old K use?")
    print(kg.to_mermaid())
"""
from .graph_engine import (
    KnowledgeGraphEngine,
    KnowledgeGraph,
    Entity,
    Relation,
    create_graph_engine
)
from .security import (
    get_security_manager,
    check_channel_permission,
    sanitize_output,
    PermissionError,
    SecurityManager
)
from .ontology import (
    OntologyManager,
    OntologyClass,
    OntologyProperty,
    get_ontology_manager,
    create_ontology_manager
)

__all__ = [
    # Graph Engine
    'KnowledgeGraphEngine',
    'KnowledgeGraph',
    'Entity',
    'Relation',
    'create_graph_engine',
    
    # Security Module
    'get_security_manager',
    'check_channel_permission',
    'sanitize_output',
    'PermissionError',
    'SecurityManager',
    
    # Ontology Module
    'OntologyManager',
    'OntologyClass',
    'OntologyProperty',
    'get_ontology_manager',
    'create_ontology_manager',
]

# Version
__version__ = '2.0.0'  # KG Engine v2.0.0