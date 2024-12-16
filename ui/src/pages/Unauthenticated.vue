<template>
  <div class="login">
    <div class="login-container">
      <p-heading tag="h1" size="lg" class="login-title">Login</p-heading>
      <form @submit.prevent="handleSubmit" class="login-form">
        <p-text-input
          v-model="password"
          type="password"
          placeholder="Enter password"
          :error="error"
          class="login-input"
        />
        <p-button
          type="submit"
          :loading="loading"
          class="login-button"
        >
          Login
        </p-button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const password = ref('')
const loading = ref(false)
const error = ref('')
const router = useRouter()

async function handleSubmit(): Promise<void> {
  if (loading.value) return

  loading.value = true
  error.value = ''

  try {
    // TODO: Implement actual login logic here
    const redirect = router.currentRoute.value.query.redirect as string
    router.push(redirect || '/')
  } catch (e) {
    error.value = 'Invalid password'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--surface-background);
}

.login-container {
  width: 100%;
  max-width: 400px;
  padding: theme(spacing.8);
  background: var(--surface-raised);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--shadow-lg);
}

.login-title {
  margin-bottom: theme(spacing.6);
  text-align: center;
  color: var(--text-default);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: theme(spacing.4);
}

.login-input {
  width: 100%;
}

.login-button {
  width: 100%;
}
</style> 