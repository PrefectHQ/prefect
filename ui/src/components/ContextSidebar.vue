<template>
  <p-context-sidebar class="context-sidebar">
    <template #header>
      <router-link :to="routes.root()" class="context-sidebar__logo-link">
        <p-icon icon="Prefect" class="context-sidebar__logo-icon" />
      </router-link>
    </template>
    <p-context-nav-item title="Dashboard" :to="routes.dashboard()" />
    <p-context-nav-item title="Runs" :to="routes.runs()" />
    <p-context-nav-item title="Flows" :to="routes.flows()" />
    <p-context-nav-item title="Deployments" :to="routes.deployments()" />
    <p-context-nav-item v-if="canSeeWorkPools" title="Work Pools" :to="routes.workPools()" />
    <p-context-nav-item v-if="!canSeeWorkPools" title="Work Queues" :to="routes.workQueues()" />
    <p-context-nav-item title="Blocks" :to="routes.blocks()" />
    <p-context-nav-item :title="localization.info.variables" :to="routes.variables()" />
    <p-context-nav-item title="Automations" :to="routes.automations()" />
    <p-context-nav-item title="Event Feed" :to="routes.events()" />
    <p-context-nav-item title="Concurrency" :to="routes.concurrencyLimits()" />

    <template #footer>
      <a href="https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss&utm_term=none&utm_content=none" target="_blank">
        <p-context-nav-item>
          <div>
            Ready to scale?
          </div>
          <p-button primary small class="context-sidebar__upgade-button">
            Upgrade
          </p-button>
        </p-context-nav-item>
      </a>

      <p-context-nav-item @click="openJoinCommunityModal">
        Join the Community
        <JoinTheCommunityModal :show-modal="showJoinCommunityModal || !joinTheCommunityModalDismissed" @update:show-modal="updateShowModal" />
      </p-context-nav-item>

      <p-context-nav-item title="Settings" :to="routes.settings()" />
    </template>
  </p-context-sidebar>
</template>

<script lang="ts" setup>
  import JoinTheCommunityModal from '@/components/JoinTheCommunityModal.vue'
  import { useCan } from '@/compositions/useCan'
  import { routes } from '@/router'
  import { PContextNavItem, PContextSidebar } from '@prefecthq/prefect-design'
  import { localization, useShowModal } from '@prefecthq/prefect-ui-library'
  import { useStorage } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'

  const can = useCan()
  const canSeeWorkPools = computed(() => can.read.work_pool)

  const { showModal: showJoinCommunityModal, open: openJoinCommunityModal } = useShowModal()
  const { value: joinTheCommunityModalDismissed } = useStorage('local', 'join-the-community-modal-dismissed', false)
  function updateShowModal(updatedShowModal: boolean): void {
    showJoinCommunityModal.value = updatedShowModal
    if (!updatedShowModal) {
      joinTheCommunityModalDismissed.value = true
    }
  }
</script>

<style>
.context-sidebar__logo-link { @apply
  outline-none
  rounded-md
  focus:ring-spacing-focus-ring
  focus:ring-focus-ring
}

.context-sidebar__logo-link:focus:not(:focus-visible) { @apply
  ring-transparent
}

.context-sidebar__logo-icon { @apply
  !w-[42px]
  !h-[42px]
}

.context-sidebar__upgade-button { @apply
  ml-auto
}
</style>