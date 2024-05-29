<template>
  <p-modal :show-modal="true" title="Join the Prefect Community">
    <template #header>
      <h2>Join the Community</h2>
    </template>

    <template #default>
      <p>
        Connect with 25k+ engineers scaling Python with Prefect. Show us your work and be the first to know about new Prefect features.
      </p>

      <div>
        <p-button primary icon="Slack">
          Join us on Slack
        </p-button>
      </div>

      <p-divider class="-my-3" />

      <p-form :id="formId" @submit="console.dir($event)">
        <p-label label="Notify me about Prefect updates">
          <p-text-input v-model="email" placeholder="hello@prefect.io" type="email" required />
        </p-label>
      </p-form>
    </template>

    <template #cancel="scope">
      <p-button class="sm:order-first" @click="scope.close">
        Skip
      </p-button>
    </template>

    <template #actions>
      <p-button primary type="submit" :form="formId">
        Sign up
      </p-button>
    </template>
  </p-modal>
</template>

<script setup lang="ts">
  import { ref } from 'vue'

  const email = ref<string>()

  const formId = 'join-the-community-modal'
</script>