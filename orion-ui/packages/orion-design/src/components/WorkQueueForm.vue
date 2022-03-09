<template>
  <div class="work-queue-form">
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
        <m-number-input v-model="internalValue.concurrencyLimit" class="work-queue-form__number-input" />
      </DetailsKeyValue>
    </div>

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

    <div class="mb-2">
      <DetailsKeyValue label="Is Active" stacked>
        <m-toggle v-model="isActive" class="work-queue-form__toggle">
          <span v-if="isActive">Active</span>
          <span v-else>Paused</span>
        </m-toggle>
      </DetailsKeyValue>
    </div>

    <template v-if="internalValue.id">
      <div class="mb-2">
        <template v-if="showDeleteButton">
          <div class="work-queue-form__danger-zone">
            <DetailsKeyValue label="Danger Zone" stacked>
              <div class="d-flex align-center font-weight-semibold mt-2 content__delete__btn">
                <i class="pi pi-information-line pi-sm mr-1 content-delete__text" />
                <span class="content-delete__text">Deleting this work queue will delete all its data stored in Cloud.</span>
              </div>

              <div class="mt-2">
                <m-button color="delete" miter @click="emit('remove', internalValue.id!)">
                  Delete Work Queue
                </m-button>
                <m-icon-button icon="pi-lg pi-close-line" class="work-queue-form__hide-delete" flat @click="showDeleteButton = false" />
              </div>
            </DetailsKeyValue>
          </div>
        </template>
        <template v-else>
          <DetailsKeyValue label="Delete Work Queue" stacked>
            <m-button class="work-queue-form__show-delete" miter @click="showDeleteButton = true">
              Show Delete Button
            </m-button>
          </DetailsKeyValue>
        </template>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import DeploymentsMultiSelect from '@/components/DeploymentsMultiSelect.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import FlowRunnerTypeMultiSelect from '@/components/FlowRunnerTypeMultiSelect.vue'
  import TagsInput from '@/components/TagsInput.vue'
  import { WorkQueueFormValues } from '@/models/WorkQueueFormValues'
  import { DeploymentsApi } from '@/services/DeploymentsApi'

  const props = defineProps<{
    values: WorkQueueFormValues,
    getDeployments: DeploymentsApi['getDeployments'],
  }>()

  const emit = defineEmits<{
    (event: 'update:workQueue', value: WorkQueueFormValues): void,
    (event: 'remove', value: string): void,
  }>()

  const showDeleteButton = ref(false)

  const deploymentsSubscription = useSubscription(props.getDeployments, [{}])
  const deployments = computed(() => deploymentsSubscription.response.value ?? [])

  const internalValue = computed({
    get() {
      return props.values
    },
    set(value: WorkQueueFormValues) {
      emit('update:workQueue', value)
    },
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

.work-queue-form__danger-zone {
  position: relative;
  color: var(--error);
  background-color: rgba(251, 78, 78, 0.3);
  padding: var(--p-2);
}

.work-queue-form__hide-delete {
  position: absolute;
  top: 10px;
  right: 10px;
}

.work-queue-form__show-delete {
  > :first-child {
    border-color: var(--error) !important;
    color: var(--error) !important;
  }
}

.work-queue-form__show-delete.active {
  > :first-child {
    color: var(--white) !important;
    background-color: var(--error) !important;
  }
}
</style>