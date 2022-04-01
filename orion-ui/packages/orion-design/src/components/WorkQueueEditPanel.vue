<template>
  <m-panel class="work-queue-edit-panel">
    <template #title>
      <i class="pi pi-robot-line pi-1x" />
      <span class="ml-1">Edit Work Queue</span>
    </template>

    <m-loader :loading="saving" class="work-queue-edit-panel__loader" />

    <section>
      <WorkQueueForm
        v-model:values="workQueueFormValues"
        :deployments-api="deploymentsApi"
        @remove="remove"
      />
    </section>

    <template #actions="{ close }">
      <m-button miter @click="close">
        Cancel
      </m-button>
      <m-button color="primary" miter :loading="saving" @click="update">
        Save
      </m-button>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { ref } from 'vue'
  import WorkQueueForm from '@/components/WorkQueueForm.vue'
  import { WorkQueue } from '@/models/WorkQueue'
  import { WorkQueueFormValues } from '@/models/WorkQueueFormValues'
  import { DeploymentsApi } from '@/services/DeploymentsApi'
  import { WorkQueuesApi } from '@/services/WorkQueuesApi'
  import { closePanel, exitPanel } from '@/utilities/panels'
  import { WorkQueuesListSubscription, WorkQueueSubscription } from '@/utilities/subscriptions'
  import { showToast } from '@/utilities/toasts'

  const props = defineProps<{
    workQueue: WorkQueue,
    workQueueSubscription: WorkQueueSubscription,
    workQueuesListSubscription: WorkQueuesListSubscription,
    deploymentsApi: DeploymentsApi,
    workQueuesApi: WorkQueuesApi,
  }>()

  const saving = ref(false)
  const workQueueFormValues = ref(new WorkQueueFormValues({ ...props.workQueue }))

  async function update(): Promise<void> {
    try {
      saving.value = true
      await props.workQueuesApi.updateWorkQueue(props.workQueue.id, workQueueFormValues.value.getWorkQueueRequest())
      await props.workQueueSubscription.refresh()
      props.workQueuesListSubscription.refresh()
      showToast('Updated Work Queue', 'success')
      closePanel()
    } catch (err) {
      console.warn('error with updating work queue', err)
      showToast('Error with updating work queue', 'error')
    } finally {
      saving.value = false
    }
  }

  async function remove(id: string): Promise<void> {
    try {
      saving.value = true
      await props.workQueuesApi.deleteWorkQueue(id)
      props.workQueuesListSubscription.refresh()
      showToast('Deleted Work Queue', 'success')
      exitPanel()
    } catch (err) {
      console.warn('error with deleting work queue', err)
      showToast('Error with deleting work queue', 'error')
    } finally {
      saving.value = false
    }
  }
</script>

<style lang="scss">
.work-queue-edit-panel__loader {
  position: absolute !important;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>