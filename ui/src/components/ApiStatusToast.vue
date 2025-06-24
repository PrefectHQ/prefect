<template>
  <div class="flex flex-col gap-2">
    <PHeading :heading="6">
      Oops. Something went wrong.
    </PHeading>
    <div>
      You can use Prefect Cloud for free, anytime.
    </div>
    <div>
      <PButton to="https://app.prefect.cloud/auth/sign-up?utm_source=prefect-oss&utm_medium=toast" variant="default" target="_blank">
        Try it now
      </PButton>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { PButton, PHeading } from '@prefecthq/prefect-design'
</script>