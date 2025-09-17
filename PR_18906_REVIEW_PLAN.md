# PR #18906 Review Feedback - Comprehensive Plan

## Overview
Alex's review identified several fundamental issues with our V1→V2 adapter implementation. The core problems stem from:
1. Confusing logic flow mixing V1 and V2 code paths
2. Incorrect assumptions about V1/V2 coexistence post-migration
3. Missing protocol definitions causing unnecessary fallback code
4. Broken increment logic that requires ALL limits be V2

## Critical Issues to Address

### 1. Dead Code Removal
**Location:** `src/prefect/server/api/concurrency_limits.py` lines 122-135
**Issue:** Unreachable code after return statement
**Fix:** Delete lines 123-135 completely

### 2. Protocol Enhancement
**Location:** `src/prefect/server/utilities/leasing.py` 
**Issue:** `list_holders_for_limit` method exists in implementations but not in protocol
**Fix:** 
- Add `list_holders_for_limit` to the `LeaseStorage` protocol
- Return type should be `list[ConcurrencyLeaseHolder]` for better typing
- Remove all the complex fallback code in `get_active_slots_from_leases` (lines 107-131)
- Remove fallback in `find_lease_for_task_run` (line 215)

### 3. V1/V2 Logic Separation
**Current Problem:** V1 and V2 logic is intermingled, making code hard to follow
**Pattern to Fix:**
```python
# GOOD - V2 first, early return, then V1 fallback
async def endpoint():
    # Try V2 path
    v2_result = await try_v2_operation()
    if v2_result:
        return convert_to_v1_shape(v2_result)
    
    # Fall back to V1
    v1_result = await try_v1_operation()
    if v1_result:
        return v1_result
    
    raise HTTPException(404)
```

**Specific Fixes:**
- Line 168: Remove V1 read when V2 exists (V1 shouldn't exist post-migration)
- Line 217: Move V1 fallback logic after V2 logic completes
- Line 346: Remove fallback read - if V2 exists, V1 won't
- Lines 376, 441: Add early returns after successful operations
- Line 398: Remove unnecessary V1 deletion block
- Line 685: Remove V1 cleanup when V2 path succeeds

### 4. Increment Logic Fix
**Location:** Line 510
**Current Issue:** Only uses V2 when ALL requested tags have V2 limits
**Required Fix:** Handle mixed V1/V2 scenarios:
```python
# Collect V1 and V2 limits separately
v2_limits = await get_v2_limits(v2_names)
v1_limits = await get_v1_limits(remaining_tags)

# Increment V2 limits via lease path
if v2_limits:
    await increment_v2_with_lease(v2_limits)

# Increment V1 limits via legacy path  
if v1_limits:
    await increment_v1_legacy(v1_limits)
```

### 5. Test Simplification
**Location:** `tests/server/orchestration/api/test_concurrency_limits_v1_adapter.py`
**Issue:** Using StubStorage when filesystem storage would work
**Fix:** 
- Remove StubStorage class (lines 138-162)
- Use actual filesystem storage with its `list_holders_for_limit` implementation
- Simplify test to verify actual behavior rather than mocking

### 6. Create Endpoint Cleanup
**Issue:** Mirroring into V1 table unnecessarily
**Fix:** The adapter should be V2-only. Remove lines 101-109 that create V1 records.

## Implementation Order

1. **Add protocol method** - Update `LeaseStorage` protocol with `list_holders_for_limit`
2. **Clean up dead code** - Remove unreachable code blocks
3. **Simplify logic flow** - Restructure endpoints to have clear V2→V1 fallback pattern
4. **Fix increment** - Implement mixed V1/V2 handling
5. **Update tests** - Remove stubs, use real filesystem storage
6. **Remove V1 mirroring** - Stop creating V1 records when V2 succeeds

## Key Principles

1. **V2 is primary, V1 is fallback** - Always try V2 first, fall back to V1 only if needed
2. **Post-migration assumption** - If V2 exists, V1 shouldn't (they're mutually exclusive)
3. **Early returns** - Return immediately after successful operations
4. **Clean separation** - Keep V2 logic together, V1 logic together, don't interleave
5. **Mixed mode support** - INCREMENT must handle some limits being V1 and others V2

## Testing Strategy

After fixes:
1. Verify adapter tests pass with filesystem storage (no stubs)
2. Ensure existing V1 tests continue to pass
3. Test mixed V1/V2 increment scenarios explicitly
4. Verify no V1 records are created when adapter creates V2 limits