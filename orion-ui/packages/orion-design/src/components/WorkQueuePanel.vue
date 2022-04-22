<template>
  <m-panel class="work-queue-panel">
    <template #title>
      <div class="work-queue-panel__title">
        <i class="work-queue-panel__icon pi pi-robot-line" />
        {{ workQueue?.name }}
      </div>
    </template>

    <m-loader :loading="loading || saving" class="work-queue-panel__loader" />

    <div class="work-queue-panel__details-row">
      <p>
        Work queues are defined by the set of deployments, tags, or flow runners that they filter for.
        <a href="https://orion-docs.prefect.io/concepts/work-queues/">View our docs to learn more.</a>
      </p>
    </div>

    <div class="work-queue-panel__details-row">
      <CodeBanner :code="`prefect agent start ${workQueue?.id}`" heading="Work queue is ready to go!" description="Work queues define the work to be done and agents poll a specific work queue for new work." />
    </div>
    <div class="work-queue-panel__details-row">
      <DetailsKeyValue
        label="Concurrency Limit"
        :value="workQueue ? concurrencyLimit : null"
        stacked
      />
      <WorkQueuePausedTag :work-queue="workQueue" />
    </div>
    <div class="work-queue-panel__details-row">
      <DetailsKeyValue label="Created Date" :value="createdDate" stacked />
    </div>
    <div class="work-queue-panel__details-row">
      <DetailsKeyValue label="Description" :value="workQueue?.description" stacked />
    </div>
    <div class="work-queue-panel__details-row">
      <DetailsKeyValue label="Tags" :value="workQueue?.description" stacked>
        <m-tags :tags="workQueue?.filter.tags" />
      </DetailsKeyValue>
    </div>
    <div class="work-queue-panel__details-row">
      <DetailsKeyValue label="Deployments" :value="workQueue?.description" stacked>
        <m-tags icon="pi-map-pin-line" :tags="workQueue?.filter.deploymentIds" />
      </DetailsKeyValue>
    </div>
    <div class="work-queue-panel__details-row">
      <DetailsKeyValue label="Flow Runners" :value="workQueue?.description" stacked>
        <m-tags icon="pi-lifebuoy-line" :tags="workQueue?.filter.flowRunnerTypes" />
      </DetailsKeyValue>
    </div>

    <template #actions="{ close }">
      <m-button miter @click="close">
        Close
      </m-button>
      <template v-if="can.update.work_queue">
        <m-button miter @click="open">
          <i class="pi pi-xs pi-pencil-line mr-1" /> Edit
        </m-button>
        <template v-if="workQueue?.isPaused">
          <m-button color="primary" miter @click="resume">
            <i class="pi pi-xs pi-play-line mr-1" /> Resume
          </m-button>
        </template>
        <template v-else>
          <m-button color="primary" miter :loading="saving" @click="pause">
            <i class="pi pi-xs pi-pause-line mr-1" /> Pause
          </m-button>
        </template>
      </template>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue'
  import CodeBanner from '@/components/CodeBanner.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import WorkQueuePausedTag from '@/components/WorkQueuePausedTag.vue'
  import { WorkQueue } from '@/models/WorkQueue'
  import { WorkQueuesApi } from '@/services/WorkQueuesApi'
  import { Can } from '@/types/permissions'
  import { WorkQueuesListSubscription, WorkQueueSubscription } from '@/utilities/subscriptions'

  const props = defineProps<{
    // "workQueueId" will probably come from URL soon
    workQueueId: string,
    workQueueSubscription: WorkQueueSubscription,
    workQueuesListSubscription: WorkQueuesListSubscription,
    openWorkQueueEditPanel: (workQueue: WorkQueue) => void,
    workQueuesApi: WorkQueuesApi,
    can: Can,
  }>()

  const saving = ref(false)

  const loading = computed(() => props.workQueueSubscription.loading && props.workQueueSubscription.response === undefined)
  const workQueue = computed(() => props.workQueueSubscription.response ?? null)
  const concurrencyLimit = computed(() => workQueue.value?.concurrencyLimit ? workQueue.value.concurrencyLimit.toLocaleString() : 'No Limit')
  const createdDate = computed(() => workQueue.value?.created ? workQueue.value.created.toISOString() : null)

  async function pause(): Promise<void> {
    saving.value = true
    await props.workQueuesApi.pauseWorkQueue(props.workQueueId)
    await props.workQueueSubscription.refresh()

    props.workQueuesListSubscription.refresh()

    saving.value = false
  }

  async function resume(): Promise<void> {
    saving.value = true
    await props.workQueuesApi.resumeWorkQueue(props.workQueueId)
    await props.workQueueSubscription.refresh()

    props.workQueuesListSubscription.refresh()

    saving.value = false
  }

  function open(): void {
    if (workQueue.value) {
      props.openWorkQueueEditPanel(workQueue.value)
    }
  }
</script>


<style lang="scss">
.work-queue-panel__title {
  display: flex;
  align-items: center;
  gap: var(--p-1);
}

.work-queue-panel__icon{
  color: var(--grey-40);
}

.work-queue-panel__details-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-2);
}

.work-queue-panel__preface {
  padding: var(--p-2);
}

.panel__actions {
  button {
    flex-grow: 1;
  }
}

.work-queue-panel__loader {
  position: absolute !important;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>