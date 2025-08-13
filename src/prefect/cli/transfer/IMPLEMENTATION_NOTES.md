# Transfer Command Implementation Notes

## Overview
The `prefect transfer` command needs to migrate resources between Prefect profiles while respecting dependencies and maintaining data integrity.

## Resource Dependencies

Based on the Prefect data model, resources have the following dependency relationships:

### Dependency Graph
```
Variables (independent)
Concurrency Limits (independent)
Blocks (may reference other blocks)
└── Work Pools (may reference blocks for infrastructure)
    └── Work Queues (belong to work pools)
        └── Deployments (depend on flows, work queues, blocks)
            └── Automations (depend on deployments, work pools)
```

### Key Challenges

1. **Block References**: Blocks can reference other blocks (e.g., S3 block referencing AWS credentials block)
   - Need topological sorting within blocks
   - Must map block references when transferring

2. **Flow Dependencies**: Deployments reference flows, but flows aren't simple data objects
   - Flows are Python code, not just database records
   - May need to transfer flow code separately or require flows to exist

3. **ID Mapping**: Resources reference each other by ID
   - Source IDs won't match target IDs
   - Need to maintain mapping tables during transfer

4. **Work Queues**: Work queues are children of work pools
   - Should transfer with their parent work pool
   - Need to maintain parent-child relationships

5. **Automations**: Complex dependencies on multiple resource types
   - Can reference deployments, work pools, blocks
   - May have actions that reference other resources

## Implementation Strategy

### Phase 1: Basic Structure (DONE)
- [x] Command scaffolding
- [x] Module organization
- [x] Basic resource gathering
- [x] Error handling and reporting

### Phase 2: Dependency Resolution (IN PROGRESS)
- [ ] Define proper data structures for dependency tracking
- [ ] Implement topological sorting for transfer order
- [ ] Create ID mapping system

### Phase 3: Resource Transfer Implementation
- [ ] **Variables**: Simple key-value pairs, no dependencies
- [ ] **Concurrency Limits**: Simple limits, no dependencies  
- [ ] **Blocks**: 
  - Register/verify block types in target
  - Handle block-to-block references
  - Map block IDs in data fields
- [ ] **Work Pools**:
  - Transfer work pool configurations
  - Transfer associated work queues
  - Map block references in job templates
- [ ] **Deployments**:
  - Verify flows exist or transfer flow metadata
  - Map work pool and block references
  - Transfer schedules and parameters
- [ ] **Automations**: (Cloud-only initially)
  - Map all resource references
  - Transfer triggers and actions

## Data Structure Proposal

```python
@dataclass
class TransferContext:
    """Context for managing resource transfers."""
    
    # ID mappings from source to target
    block_id_map: dict[UUID, UUID]
    work_pool_id_map: dict[UUID, UUID]
    deployment_id_map: dict[UUID, UUID]
    
    # Name mappings for lookups
    block_name_map: dict[str, str]  # source_name -> target_name
    
    # Dependency graph
    dependencies: dict[ResourceKey, set[ResourceKey]]
    
    # Transfer order (topologically sorted)
    transfer_order: list[ResourceKey]

@dataclass 
class ResourceKey:
    """Unique identifier for a resource."""
    type: ResourceType
    id: UUID
    name: str
```

## Open Questions

1. **Flow Handling**: How do we handle deployments when flows don't exist in target?
   - Option A: Fail the deployment transfer
   - Option B: Create placeholder flow reference
   - Option C: Transfer flow code (complex)

2. **Secret Handling**: How do we handle encrypted secrets in blocks?
   - Secrets can't be read from source
   - May need user to re-enter secrets after transfer

3. **Partial Transfers**: What if some resources fail?
   - Should we rollback all changes?
   - Continue with what we can?
   - Mark failed dependencies?

4. **Name Conflicts**: What if resource names already exist?
   - Current: Skip existing resources
   - Alternative: Rename with suffix
   - Alternative: Update existing

## Next Steps

1. Implement proper dependency resolution in `_dependencies.py`
2. Create TransferContext to track mappings
3. Implement resources in order of complexity:
   - Variables (simplest)
   - Concurrency Limits
   - Blocks (with type/schema mapping)
   - Work Pools
   - Deployments (most complex)