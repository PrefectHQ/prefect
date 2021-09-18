<template>
  <list-item class="list-item--flow d-flex align-start justify-start">
    <i class="item--icon pi pi-map-pin-line text--grey-40 align-self-start" />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <h2>
        {{ deployment.name }}
      </h2>

      <div
        class="
          tag-container
          font-weight-semibold
          nowrap
          caption
          d-flex
          align-bottom
        "
      >
        <span class="mr-1">
          <span class="text--grey-40">Schedule: </span>
          <span class="text--grey-80">{{ schedule }}</span>
        </span>

        <span class="mr-1">
          <span class="text--grey-40">Location: </span>
          <span class="text--grey-80">{{ location }}</span>
        </span>

        <!-- Hiding these for now since they're not in the design but I think we'll need them -->
        <!-- <Tag
          v-for="tag in tags"
          :key="tag"
          color="secondary-pressed"
          class="font--primary caption mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag> -->
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto nowrap">
      <Button outlined class="mr-1" @click="parametersDrawerActive = true">
        View Parameters
      </Button>
      <Button outlined>Quick Run</Button>
    </div>
  </list-item>

  <drawer v-model="parametersDrawerActive" show-overlay>
    <template #title>{{ deployment.name }}</template>
    <h3 class="font-weight-bold">Parameters</h3>
    <div>These are the inputs that are passed to runs of this Deployment.</div>

    <hr class="mt-2 parameters-hr align-self-stretch" />

    <Input v-model="search" placeholder="Search...">
      <template #prepend>
        <i class="pi pi-search-line"></i>
      </template>
    </Input>

    <div class="mt-2 font--secondary">
      {{ filteredParameters.length }} result{{
        filteredParameters.length !== 1 ? 's' : ''
      }}
    </div>

    <hr class="mt-2 parameters-hr" />

    <div class="parameters-container pr-2 align-self-stretch">
      <div v-for="(parameter, i) in filteredParameters" :key="i">
        <div class="d-flex align-center justify-space-between">
          <h4 class="font-weight-bold font--secondary">{{ parameter.name }}</h4>
          <span
            class="
              parameter-type
              font--secondary
              caption-small
              px-1
              text--white
            "
          >
            {{ parameter.type }}
          </span>
        </div>

        <p class="font--secondary">
          {{ parameter.parameter }}
        </p>

        <hr
          v-if="i !== filteredParameters.length - 1"
          class="mb-2 parameters-hr"
        />
      </div>
    </div>
  </drawer>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { Deployment } from '@/objects'

class Props {
  deployment = prop<Deployment>({ required: true })
}

@Options({
  watch: {
    parametersDrawerActive() {
      this.search = ''
    }
  }
})
export default class ListItemDeployment extends Vue.with(Props) {
  parametersDrawerActive: boolean = false
  search: string = ''

  get location(): string {
    return this.deployment.location
  }

  get parameters(): { [key: string]: any }[] {
    return this.deployment.parameters
  }

  get schedule(): any {
    return this.deployment.schedule
  }

  get tags(): string[] {
    return this.deployment.tags
  }

  get filteredParameters(): { [key: string]: any }[] {
    return this.parameters.filter(
      (p) => p.name.includes(this.search) || p.type.includes(this.search)
    )
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--deployment.scss';
</style>
