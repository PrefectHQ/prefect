<template>
  <div class="flow-runs-filter">
    <div class="flow-runs-filter__date-filters">
      <p-label label="Start Date">
        <PDateInput v-model="startDate" show-time />
      </p-label>
      <p-label label="End Date">
        <PDateInput v-model="endDate" show-time />
      </p-label>
    </div>
    <div class="flow-runs-filter__meta-filters">
      <StateSelect v-model:selected="states" empty-message="All run states" />
      <FlowCombobox v-model:selected="flows" empty-message="All flows" />
      <DeploymentCombobox v-model:selected="deployments" empty-message="All deployments" />
      <PTagsInput v-model="tags" empty-message="All Tags" inline />
      <template v-if="!media.md">
        <SearchInput v-model="name" placeholder="Search by run name" label="Search by run name" />
      </template>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { StateSelect, DeploymentCombobox, FlowCombobox, SearchInput, useFlowRunFilterFromRoute } from '@prefecthq/orion-design'
  import { PTagsInput, PDateInput, media } from '@prefecthq/prefect-design'

  const { startDate, endDate, states, deployments, flows, tags, name } = useFlowRunFilterFromRoute()
</script>

<style>
.flow-runs-filter,
.flow-runs-filter__date-filters,
.flow-runs-filter__meta-filters { @apply
  grid
  gap-2
}

.flow-runs-filter__date-filters { @apply
  grid-cols-2
}

.flow-runs-filter__meta-filters { @apply
  grid-cols-1
}

@screen md {
  .flow-runs-filter__meta-filters { @apply
    grid-cols-4
  }
}
</style>