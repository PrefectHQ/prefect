<template>
  <p-modal v-model:show-modal="showModal" title="Join the Prefect Community">
    <template #header>
      <h2>Join the Community</h2>
    </template>

    <template #default>
      <p>
        Connect with 25k+ engineers scaling Python with Prefect. Show us your work and be the first to know about new Prefect features.
      </p>

      <div class="flex gap-x-2 items-center">
        <p-button primary icon="Slack" :to="joinSlackUrl" target="_blank" @click="showJoinSlackThankYouMessage = true">
          Join us on Slack
        </p-button>

        <span v-if="showJoinSlackThankYouMessage" class="text-sm italic">
          Thanks for joining our community!
        </span>
      </div>

      <p-divider class="-my-3" />

      <p-form :id="formId" @submit="signUpForEmailUpdates">
        <p-label v-slot="{ id }" label="Notify me about Prefect updates">
          <p-text-input :id v-model="email" placeholder="hello@prefect.io" type="email" required />
        </p-label>
      </p-form>

      <p-message v-if="error" error>
        {{ error }}
      </p-message>
    </template>

    <template #cancel="scope">
      <p-button class="sm:order-first" @click="scope.close">
        Skip
      </p-button>
    </template>

    <template #actions>
      <p-button primary type="submit" :form="formId" :loading>
        Sign up
      </p-button>
    </template>
  </p-modal>
</template>

<script setup lang="ts">
  import { ref } from 'vue'

  const showModal = defineModel<boolean>('showModal')

  const joinSlackUrl = 'http://prefect.io/slack?utm_source=oss&utm_medium=oss&utm_campaign=oss_popup&utm_term=none&utm_content=none'
  const showJoinSlackThankYouMessage = ref(false)

  const formId = 'join-the-community-modal'
  const email = ref<string>()

  const loading = ref(false)
  const error = ref('')

  const formEndpoint = 'https://getform.io/f/eapderva'
  async function signUpForEmailUpdates(): Promise<void> {
    error.value = ''
    loading.value = true
    try {
      const response = await fetch(formEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.value }),
        // getform redirects to a thank-you page so this cancels that additional request
        redirect: 'manual',
      })

      console.dir(response)
    } catch (err) {
      error.value = 'An error occurred. Please try again.'
      console.error(err)
    } finally {
      loading.value = false
    }
  }
</script>