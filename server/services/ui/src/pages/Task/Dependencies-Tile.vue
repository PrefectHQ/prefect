<script>
import CardTitle from '@/components/Card-Title'
import SchematicFlow from '@/components/Schematics/Schematic-Flow'

export default {
  filters: {
    typeClass: val => val.split('.').pop()
  },
  components: {
    CardTitle,
    SchematicFlow
  },
  props: {
    downstreamCount: {
      type: Number,
      required: false,
      default: () => null
    },
    loading: {
      type: Boolean,
      required: false,
      default: () => false
    },
    tasks: {
      type: Array,
      required: true
    },
    upstreamCount: {
      type: Number,
      required: false,
      default: () => null
    }
  },
  data() {
    return {
      expanded: true,
      task: this.tasks.find(task => task.id == this.$route.params.id)
    }
  },
  computed: {
    subtitle() {
      return `${this.upstreamCount} Upstream • ${this.downstreamCount} Downstream`
    }
  },
  watch: {
    $route(val) {
      if (!val.query.schematic) return (this.task = null)
      this.task = this.tasks.find(
        task => task.id == this.$route.query.schematic
      )
    },
    tasks() {
      if (!this.$route.query.schematic) return (this.task = null)

      this.task = this.tasks.find(
        task => task.id == this.$route.query.schematic
      )
    }
  },
  methods: {}
}
</script>

<template>
  <v-card class="pa-2" tile>
    <CardTitle title="Dependencies" icon="share" :subtitle="subtitle">
      <v-chip
        slot="badge"
        class="body-2 white--text font-weight-bold badge"
        color="accentOrange"
      >
        Beta
      </v-chip>
    </CardTitle>

    <v-card-text class="full-height position-relative">
      <SchematicFlow v-if="!loading" :tasks="tasks" />
      <v-skeleton-loader v-else type="image" />

      <!-- Could probably componentize this at some point -->
      <v-card v-if="task" class="task-tile position-absolute" tile>
        <v-list-item
          dense
          class="py-2 pr-2 pl-5"
          :to="{ name: 'task', params: { id: task.id } }"
        >
          <v-list-item-content class="my-0 py-0">
            <v-list-item-subtitle class="caption mb-0">
              Task
            </v-list-item-subtitle>
            <v-list-item-title>
              {{ task.name }}
            </v-list-item-title>
            <v-list-item-subtitle
              v-if="task.id == $route.params.id"
              class="caption mb-0"
            >
              (Current Task)
            </v-list-item-subtitle>
          </v-list-item-content>
        </v-list-item>

        <v-divider></v-divider>

        <v-card-text class="pb-0 px-3 caption">
          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Mapped:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.mapped ? 'Yes' : 'No' }}
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Max retries:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.max_retries }}
            </v-col>
          </v-row>

          <v-row v-if="task.max_retries > 0">
            <v-col cols="6" class="pt-0">
              <span class="black--text">Retry delay:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.retry_delay }}
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Class:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.type | typeClass }}
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Trigger:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.trigger | typeClass }}
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </v-card-text>
  </v-card>
</template>

<style lang="scss" scoped>
.full-height {
  min-height: 68vh;
}

.task-tile {
  right: 1rem;
  top: 1rem;
  width: 250px;
}

.position-relative {
  position: relative;
}

.position-absolute {
  position: absolute;
}
</style>
