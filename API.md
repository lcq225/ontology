# KG Engine v2.0 API Documentation

> **版本：** v2.0.0  
> **日期：** 2026-04-06  
> **状态：** 综合联动检查 7/7 通过

---

## 📖 目录

1. [Validator API](#validator-api)
2. [Contract API](#contract-api)
3. [Bus API](#bus-api)
4. [Planner API](#planner-api)
5. [Commitment API](#commitment-api)
6. [示例代码](#示例代码)

---

## Validator API

### OntologyValidator

**文件：** `core/validator.py`

**导入：**
```python
from core.validator import OntologyValidator, ValidationResult
```

---

#### `__init__(schema_path: str)`

初始化验证器。

**参数：**
- `schema_path` - Schema YAML 文件路径

**示例：**
```python
validator = OntologyValidator('schema/ontology_schema.yaml')
```

---

#### `validate_entity(entity_type: str, data: Dict) -> ValidationResult`

验证实体。

**参数：**
- `entity_type` - 实体类型（如 "Knowledge"）
- `data` - 实体数据字典

**返回：**
- `ValidationResult` - 验证结果

**示例：**
```python
result = validator.validate_entity("Knowledge", {
    "category": "milestone",
    "content": "Ontology v2.0 完成"
})

if result.valid:
    print("✅ 通过")
else:
    print(f"❌ 失败：{result.errors}")
```

---

#### `validate_relation(relation_type: str, from_type: str, to_type: str) -> ValidationResult`

验证关系。

**参数：**
- `relation_type` - 关系类型
- `from_type` - 源实体类型
- `to_type` - 目标实体类型

**返回：**
- `ValidationResult` - 验证结果

**示例：**
```python
result = validator.validate_relation("works_at", "Person", "Company")
```

---

#### `load_schema() -> Dict`

加载 Schema。

**返回：**
- `Dict` - Schema 字典

**示例：**
```python
schema = validator.load_schema()
print(f"实体类型：{list(schema['entities'].keys())}")
```

---

## Contract API

### ContractManager

**文件：** `core/contract.py`

**导入：**
```python
from core.contract import ContractManager, SkillContract, ContractResult
```

---

#### `register_contract(contract: SkillContract) -> ContractResult`

注册技能契约。

**参数：**
- `contract` - 技能契约对象

**返回：**
- `ContractResult` - 注册结果

**示例：**
```python
manager = ContractManager()

contract = SkillContract(
    skill_name="self_evolution",
    reads=["Knowledge"],
    writes=["Knowledge", "Experience"]
)

result = manager.register_contract(contract)
```

---

#### `validate_contract(contract: SkillContract) -> ContractResult`

验证契约。

**参数：**
- `contract` - 技能契约对象

**返回：**
- `ContractResult` - 验证结果

**示例：**
```python
result = manager.validate_contract(contract)
```

---

#### `check_permission(skill: str, action: str, entity: str) -> bool`

检查权限。

**参数：**
- `skill` - 技能名称
- `action` - 操作（read/write）
- `entity` - 实体类型

**返回：**
- `bool` - 是否允许

**示例：**
```python
allowed = manager.check_permission("self_evolution", "write", "Knowledge")
```

---

#### `get_dependencies(skill: str) -> Set[str]`

获取依赖。

**参数：**
- `skill` - 技能名称

**返回：**
- `Set[str]` - 依赖的技能集合

**示例：**
```python
deps = manager.get_dependencies("self_evolution")
```

---

#### `get_dependents(skill: str) -> Set[str]`

获取被依赖。

**参数：**
- `skill` - 技能名称

**返回：**
- `Set[str]` - 被依赖的技能集合

**示例：**
```python
dependents = manager.get_dependents("memorycoreclaw")
```

---

### SkillContract

**数据类：**
```python
@dataclass
class SkillContract:
    skill_name: str
    reads: List[str] = field(default_factory=list)
    writes: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
```

---

## Bus API

### EventBus

**文件：** `core/bus.py`

**导入：**
```python
from core.bus import EventBus, OntologyEvent, EventTypes
```

---

#### `__init__(enable_async: bool = False, log_events: bool = True)`

初始化事件总线。

**参数：**
- `enable_async` - 是否启用异步处理
- `log_events` - 是否记录事件日志

**示例：**
```python
bus = EventBus(enable_async=True)
```

---

#### `subscribe(subscriber: str, callback: Callable, event_types: List[str] = None)`

订阅事件。

**参数：**
- `subscriber` - 订阅者名称
- `callback` - 回调函数
- `event_types` - 订阅的事件类型列表

**示例：**
```python
def on_knowledge_created(event: OntologyEvent):
    print(f"收到事件：{event.entity_id}")

bus.subscribe("smart_reminder", on_knowledge_created,
              event_types=["knowledge_created"])
```

---

#### `publish(event: OntologyEvent)`

发布事件。

**参数：**
- `event` - 事件对象

**示例：**
```python
event = OntologyEvent(
    event_type="knowledge_created",
    entity_type="Knowledge",
    entity_id="k_001",
    source_skill="self_evolution"
)

bus.publish(event)
```

---

#### `get_event_count() -> int`

获取事件数量。

**返回：**
- `int` - 事件总数

**示例：**
```python
count = bus.get_event_count()
```

---

#### `shutdown()`

关闭事件总线。

**示例：**
```python
bus.shutdown()
```

---

### OntologyEvent

**数据类：**
```python
@dataclass
class OntologyEvent:
    event_type: str
    entity_type: str
    entity_id: str = ""
    action: str = ""
    data: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source_skill: str = ""
    priority: str = "normal"
```

---

## Planner API

### OntologyPlanner

**文件：** `core/planner.py`

**导入：**
```python
from core.planner import OntologyPlanner, Transaction, Operation
```

---

#### `__init__(validator, contract_manager, event_bus)`

初始化规划器。

**参数：**
- `validator` - OntologyValidator 实例
- `contract_manager` - ContractManager 实例
- `event_bus` - EventBus 实例

**示例：**
```python
planner = OntologyPlanner(validator, contract_manager, event_bus)
```

---

#### `create_transaction(description: str, skill_name: str) -> Transaction`

创建事务。

**参数：**
- `description` - 事务描述
- `skill_name` - 技能名称

**返回：**
- `Transaction` - 事务对象

**示例：**
```python
txn = planner.create_transaction("数据迁移", "self_evolution")
```

---

#### `add_operation(txn: Transaction, action: str, entity_type: str, data: Dict = None)`

添加操作。

**参数：**
- `txn` - 事务对象
- `action` - 操作（create/update/delete）
- `entity_type` - 实体类型
- `data` - 实体数据

**示例：**
```python
planner.add_operation(
    txn, 'create', 'Knowledge',
    data={
        "category": "milestone",
        "content": "Ontology v2.0"
    }
)
```

---

#### `validate_plan(txn: Transaction) -> ValidationResult`

验证规划。

**参数：**
- `txn` - 事务对象

**返回：**
- `ValidationResult` - 验证结果

**示例：**
```python
result = planner.validate_plan(txn)
if not result.success:
    print(f"❌ 失败：{result.errors}")
```

---

#### `execute_plan(txn: Transaction) -> ExecutionResult`

执行规划。

**参数：**
- `txn` - 事务对象

**返回：**
- `ExecutionResult` - 执行结果

**示例：**
```python
result = planner.execute_plan(txn)
if result.success:
    print(f"✅ 成功：{txn.state.value}")
else:
    print(f"❌ 失败：{result.errors}")
```

---

### Transaction

**数据类：**
```python
@dataclass
class Transaction:
    txn_id: str
    description: str
    skill_name: str
    operations: List[Operation] = field(default_factory=list)
    state: TransactionState = TransactionState.PENDING
    execution_log: List[str] = field(default_factory=list)
```

---

## Commitment API

### CommitmentManager

**文件：** `core/commitment.py`

**导入：**
```python
from core.commitment import CommitmentManager, Commitment, CommitmentType, CommitmentState
```

---

#### `create_commitment(...) -> Commitment`

创建承诺。

**参数：**
- `type` - 承诺类型（CommitmentType）
- `description` - 承诺描述
- `debtor` - 承诺方
- `creditor` - 受诺方
- `action` - 承诺行动（可选）
- `resource` - 承诺资源（可选）
- `constraint` - 承诺约束（可选）
- `quality` - 承诺质量（可选）
- `due_date` - 截止日期（可选）

**返回：**
- `Commitment` - 承诺对象

**示例：**
```python
cmt = manager.create_commitment(
    type=CommitmentType.ACTION,
    description="完成开发",
    debtor="knowledge-graph",
    creditor="User",
    action="实现功能",
    due_date="2026-04-05"
)
```

---

#### `accept_commitment(commitment_id: str) -> CommitmentResult`

接受承诺。

**参数：**
- `commitment_id` - 承诺 ID

**返回：**
- `CommitmentResult` - 结果

---

#### `start_commitment(commitment_id: str) -> CommitmentResult`

开始执行承诺。

---

#### `fulfill_commitment(commitment_id: str, evidence: List[str]) -> CommitmentResult`

履行承诺。

**参数：**
- `commitment_id` - 承诺 ID
- `evidence` - 履行证据列表

---

#### `violate_commitment(commitment_id: str, reason: str) -> CommitmentResult`

标记承诺违反。

---

#### `cancel_commitment(commitment_id: str) -> CommitmentResult`

取消承诺。

---

#### `get_commitments_by_debtor(debtor: str) -> List[Commitment]`

按承诺方查询。

---

#### `get_commitments_by_creditor(creditor: str) -> List[Commitment]`

按受诺方查询。

---

#### `get_commitment_stats() -> Dict`

获取统计。

**返回：**
```python
{
    'total': 10,
    'by_state': {'fulfilled': 5, ...},
    'by_type': {'action': 3, ...},
    'by_debtor': {'knowledge-graph': 2, ...}
}
```

---

## 示例代码

### 完整示例

```python
from core.validator import OntologyValidator
from core.contract import ContractManager, SkillContract
from core.bus import EventBus
from core.planner import OntologyPlanner
from core.commitment import CommitmentManager, CommitmentType

# 初始化
validator = OntologyValidator('schema/ontology_schema.yaml')
contract_manager = ContractManager()
event_bus = EventBus(enable_async=True)
planner = OntologyPlanner(validator, contract_manager, event_bus)
commitment_manager = CommitmentManager()

# 注册契约
contract = SkillContract(
    skill_name="self_evolution",
    reads=["Knowledge"],
    writes=["Knowledge", "Experience"]
)
contract_manager.register_contract(contract)

# 创建承诺
cmt = commitment_manager.create_commitment(
    type=CommitmentType.ACTION,
    description="完成开发",
    debtor="knowledge-graph",
    creditor="User"
)

# 创建事务
txn = planner.create_transaction("完成承诺", "self_evolution")

# 添加操作
planner.add_operation(
    txn, 'create', 'Knowledge',
    data={
        "category": "milestone",
        "content": "Ontology v2.0"
    }
)

# 验证并执行
result = planner.validate_plan(txn)
if result.success:
    result = planner.execute_plan(txn)
    print(f"✅ 事务完成：{txn.state.value}")

# 履行承诺
commitment_manager.fulfill_commitment(cmt.commitment_id, [
    "代码已提交",
    "测试通过"
])

# 发布事件
event_bus.publish(OntologyEvent(
    event_type="commitment_fulfilled",
    entity_type="Commitment",
    entity_id=cmt.commitment_id
))

# 清理
event_bus.shutdown()
```

---

**文档版本：** v2.0  
**最后更新：** 2026-03-29  
**作者：** 老 K
