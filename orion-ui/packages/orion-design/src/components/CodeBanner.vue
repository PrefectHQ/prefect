<template>
  <div class="code-banner">
    <template v-if="heading || description">
      <div class="code-banner__info">
        <div class="code-banner__info-title font-weight-semibold">
          {{ heading }}
        </div>
        <div>
          {{ description }}
        </div>
      </div>
    </template>

    <div class="code-banner__terminal">
      <div class="code-banner__window-bar">
        <svg
          width="54"
          height="12"
          viewBox="0 0 54 12"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="6" cy="6" r="6" fill="#FB4E4E" />
          <circle cx="27" cy="6" r="6" fill="#F6A609" />
          <circle cx="48" cy="6" r="6" fill="#2AC769" />
        </svg>
        <CopyButton class="code-banner__copy-btn" :value="code ?? ''" />
      </div>
      <div class="code-banner__code">
        {{ code ?? '$' }}
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import CopyButton from '@/components/CopyButton.vue'

  defineProps<{ code?: string, heading?: string, description?: string }>()
</script>

<style lang="scss">
.code-banner {
  margin: 0 auto;
  min-height: 160px;
  border-radius: 4px;
  position: relative;
  color: var(--white);

  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;

  background: var(--primary) url(/images/constellations.svg) center;
  background-size: 350px, contain;
}

.code-banner__info {
  text-align: center;
  margin-top: var(--m-3);
  width: 90%;
  max-width: 500px;
  line-height: 28px;
}

.code-banner__info-title {
  font-size: 24px;
}

.code-banner__terminal {
  padding: var(--p-2) var(--p-1);
  margin-top: var(--m-3);
  background-color: #080423;
  border-radius: 4px 4px 0 0;
  width: 95%;
  max-width: 500px;
}

.code-banner__window-bar {
  display: flex;
  justify-content: space-between;
}

.code-banner__copy-btn {
  color: var(--white);
}

.code-banner__code {
  font-family: var(--font--secondary);
  margin: var(--m-1) var(--m-4);
  position: relative;

  &::after {
    content: "";
    position: absolute;
    margin-left: 4px;
    width: 7px;
    height: 24px;
    background-color: var(--grey-80);
    display: inline-block;
    animation: blink 1.2s steps(2) infinite;
  }
}

@keyframes blink {
  0% {
    opacity: 0;
  }
}
</style>