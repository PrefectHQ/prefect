<template>
  <div class="flex items-center justify-center min-h-screen">
    <div class="w-full max-w-[400px] p-8 m-4 bg-surface-raised rounded-lg shadow-lg">
      <p-heading tag="h1" size="lg" class="mb-6 text-center text-default">
        Login
      </p-heading>
      <form @submit.prevent="handleSubmit" class="flex flex-col gap-4">
        <p-text-input
          v-model="password"
          type="password"
          placeholder="Enter password"
          :error="error"
          autofocus
          class="w-full"
        />
        <p-button
          type="submit"
          :loading="loading"
          class="w-full"
        >
          Login
        </p-button>
      </form>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePrefectApi } from '@/compositions/usePrefectApi'

const props = defineProps<{
  redirect?: string
}>()

const password = ref('')
const loading = ref(false)
const error = ref('')
const router = useRouter()
const api = usePrefectApi()

const handleSubmit = async (): Promise<void> => {
  if (loading.value) return

  loading.value = true
  error.value = ''

  try {
    localStorage.setItem('prefect-password', btoa(password.value))
    router.push(props.redirect || '/')
  } catch (e) {
    localStorage.removeItem('prefect-password')
    error.value = 'Invalid password'
  } finally {
    loading.value = false
  }
}
</script>

<style>
</style>