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
        :deployments-api="deploymentsApi"
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
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { ref } from 'vue'
  import WorkQueueEditPanel from '@/components/WorkQueueEditPanel.vue'
  import WorkQueueForm from '@/components/WorkQueueForm.vue'
  import WorkQueuePanel from '@/components/WorkQueuePanel.vue'
  import { isExistingHandleError } from '@/models/ExistingHandleError'
  import { WorkQueue } from '@/models/WorkQueue'
  import { WorkQueueFormValues } from '@/models/WorkQueueFormValues'
  import { DeploymentsApi } from '@/services/DeploymentsApi'
  import { WorkQueuesApi } from '@/services/WorkQueuesApi'
  import { exitPanel, showPanel } from '@/utilities/panels'
  import { WorkQueuesListSubscription } from '@/utilities/subscriptions'
  import { showToast } from '@/utilities/toasts'

  const props = defineProps<{
    workQueuesListSubscription: WorkQueuesListSubscription,
    workQueuesApi: WorkQueuesApi,
    deploymentsApi: DeploymentsApi,
  }>()

  const saving = ref(false)
  const workQueueFormValues = ref(new WorkQueueFormValues())

  function openWorkQueueEditPanel(workQueue: WorkQueue): void {
    const workQueueSubscription = useSubscription(props.workQueuesApi.getWorkQueue, [workQueue.id])

    showPanel(WorkQueueEditPanel, {
      workQueue,
      workQueueSubscription,
      workQueuesListSubscription: props.workQueuesListSubscription,
      workQueuesApi: props.workQueuesApi,
      deploymentsApi: props.deploymentsApi,
    })
  }

  function openWorkQueuePanel(workQueueId: string): void {
    const workQueueSubscription = useSubscription(props.workQueuesApi.getWorkQueue, [workQueueId])

    showPanel(WorkQueuePanel, {
      workQueueId,
      workQueueSubscription,
      openWorkQueueEditPanel,
      workQueuesListSubscription: props.workQueuesListSubscription,
      workQueuesApi: props.workQueuesApi,
    })
  }

  async function createWorkQueue(): Promise<void> {
    try {
      saving.value = true
      const workQueue = await props.workQueuesApi.createWorkQueue(workQueueFormValues.value.getWorkQueueRequest())
      props.workQueuesListSubscription.refresh()
      showToast('Created Work Queue', 'success')
      exitPanel()
      openWorkQueuePanel(workQueue.id)
    } catch (err) {
      if (isExistingHandleError(err)) {
        showToast(err.response.data.detail, 'error')
      } else {
        showToast('Error with creating work queue', 'error')
      }
      console.warn('error with creating work queue', err)
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