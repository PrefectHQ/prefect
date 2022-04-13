<template>
  <div class="work-queue-form">
    <div class="mb-2">
      <m-toggle v-model="isActive" class="work-queue-form__toggle">
        <span v-if="isActive">Active</span>
        <span v-else>Paused</span>
      </m-toggle>
    </div>

    <div class="mb-2">
      <DetailsKeyValue label="Name" stacked>
        <m-input v-model="internalValue.name" placeholder="" class="work-queue-form__text-input" />
      </DetailsKeyValue>
    </div>

    <div class="mb-2">
      <DetailsKeyValue label="Description" stacked>
        <TextArea v-model="internalValue.description" placeholder="" class="work-queue-form__textarea" />
      </DetailsKeyValue>
    </div>

    <div class="mb-2">
      <DetailsKeyValue label="Concurrency Limit (optional)" stacked>
        <m-input v-model="concurrencyLimit" class="work-queue-form__number-input" placeholder="No Limit" />
        <ValidationMessage
          :errors="concurrencyLimitErrors"
          :suggest="{ text: `use 'No Limit'` }"
          @apply="concurrencyLimit = $event"
        />
      </DetailsKeyValue>
    </div>

    <LabelWrapper label="Filters" class="mt-4 mb-2">
      <ValidationMessage class="work-queue-form__validation-warning" :errors="filterErrors" />

      <div class="mb-2">
        <DetailsKeyValue label="Tags" stacked>
          <TagsInput v-model:tags="internalValue.filter.tags" />
        </DetailsKeyValue>
      </div>

      <div class="mb-2">
        <DetailsKeyValue label="Flow Runner Types" stacked>
          <FlowRunnerTypeMultiSelect v-model:selectedFlowRunnerTypes="internalValue.filter.flowRunnerTypes" />
        </DetailsKeyValue>
      </div>

      <div class="mb-2">
        <DetailsKeyValue label="Select Deployment(s)" stacked>
          <DeploymentsMultiSelect v-model:selectedDeploymentIds="internalValue.filter.deploymentIds" :deployments="deployments" />
        </DetailsKeyValue>
      </div>
    </LabelWrapper>
    <template v-if="internalValue.id">
      <DeleteSection label="Work Queue" @remove="emit('remove', internalValue.id!)" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import DeleteSection from '@/components/DeleteSection.vue'
  import DeploymentsMultiSelect from '@/components/DeploymentsMultiSelect.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import FlowRunnerTypeMultiSelect from '@/components/FlowRunnerTypeMultiSelect.vue'
  import LabelWrapper from '@/components/LabelWrapper.vue'
  import TagsInput from '@/components/TagsInput.vue'
  import ValidationMessage from '@/components/ValidationMessage.vue'
  import { WorkQueueFormValues } from '@/models/WorkQueueFormValues'
  import { DeploymentsApi } from '@/services/DeploymentsApi'

  const props = defineProps<{
    values: WorkQueueFormValues,
    deploymentsApi: DeploymentsApi,
  }>()

  const emit = defineEmits<{
    (event: 'update:workQueue', value: WorkQueueFormValues): void,
    (event: 'remove', value: string): void,
  }>()


  const deploymentsSubscription = useSubscription(props.deploymentsApi.getDeployments, [{}])
  const deployments = computed(() => deploymentsSubscription.response ?? [])

  const internalValue = computed({
    get() {
      return props.values
    },
    set(value: WorkQueueFormValues) {
      emit('update:workQueue', value)
    },
  })

  const concurrencyLimit = computed({
    get() {
      return internalValue.value.concurrencyLimit?.toLocaleString()
    },
    set(value: string | undefined) {
      const intValue = value ? parseInt(value) : NaN

      if (isNaN(intValue)) {
        internalValue.value.concurrencyLimit = null
      } else {
        internalValue.value.concurrencyLimit = intValue
      }
    },
  })
  const concurrencyLimitErrors = computed(() => {
    if (internalValue.value.concurrencyLimit === null) {
      return []
    }

    const errors: string[] = []

    if (internalValue.value.concurrencyLimit < 0) {
      errors.push('Concurrency limit cannot be negative')
    } else if (internalValue.value.concurrencyLimit === 0) {
      errors.push('Concurrency limit cannot be zero')
    }

    return errors
  })

  const filterErrors = computed(() => {
    const { tags, deploymentIds, flowRunnerTypes } = internalValue.value.filter
    if (!tags.length  && !deploymentIds.length  && !flowRunnerTypes.length) {
      return ['Work Queues without filters collect all scheduled runs for all deployments.']
    }
    return []
  })

  const isActive = computed({
    get() {
      return !internalValue.value.isPaused
    },
    set(value) {
      internalValue.value.isPaused = !value
    },
  })
</script>

<style lang="scss">
.work-queue-form__toggle {
  position: relative;
  height: 30px;
}

.work-queue-form__number-input {
  width: 100%;
}

.work-queue-form__textarea {
  width: 100%;
  margin-inline-start: 0;

  .textarea__miter {
    width: 100%;
  }

  textarea {
    resize: vertical;
    white-space: normal;
  }
}

.work-queue-form__validation-warning {
  color: var(--log-level-warning);
  font-weight: bold;
}
</style>