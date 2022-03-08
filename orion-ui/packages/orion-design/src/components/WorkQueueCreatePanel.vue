<template>
  <m-panel class="work-queue-create-panel">
    <template #title>
      <i class="pi pi-robot-line pi-1x" />
      <span class="ml-1">New Work Queue</span>
    </template>

    <m-loader :loading="saving" class="work-queue-create-panel__loader" />

    <section>
      <WorkQueueForm
        v-model:values="workQueueFormValues"
        :get-deployments="getDeployments"
      />
    </section>

    <template #actions="{ close }">
      <m-button miter @click="close">
        Cancel
      </m-button>
      <m-button color="primary" miter :loading="saving" @click="createWorkQueue">
        Save
      </m-button>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { ref } from 'vue'
  import WorkQueueForm from '@/components/WorkQueueForm.vue'
  import { Deployment } from '@/models/Deployment'
  import { WorkQueue } from '@/models/WorkQueue'
  import { WorkQueueFormValues } from '@/models/WorkQueueFormValues'
  import { UnionFilters } from '@/services/Filter'
  import { IWorkQueueRequest } from '@/services/WorkQueuesApi'
  import { exitPanel } from '@/utilities/panels'
  import { WorkQueuesListSubscription } from '@/utilities/subscriptions'
  import { showToast } from '@/utilities/toasts'

  const props = defineProps<{
    workQueuesListSubscription: WorkQueuesListSubscription,
    getDeployments: (filter: UnionFilters) => Promise<Deployment[]>,
    createWorkQueue: (request: IWorkQueueRequest) => Promise<WorkQueue>,
  }>()

  const saving = ref(false)
  const workQueueFormValues = ref(new WorkQueueFormValues())

  async function createWorkQueue(): Promise<void> {
    try {
      saving.value = true
      await props.createWorkQueue(workQueueFormValues.value.getWorkQueueRequest())
      props.workQueuesListSubscription.refresh()
      showToast('Created Work Queue')
      exitPanel()
    } catch (err) {
      console.warn('error with creating work queue', err)
      showToast('Error with creating work queue', 'error')
    } finally {
      saving.value = false
    }
  }
</script>

<style lang="scss">
.work-queue-create-panel__loader {
  position: absolute !important;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>