<script>
import CardTitle from '@/components/Card-Title'
export default {
  components: {
    CardTitle
  },
  filters: {
    typeClass: val => val.split('.').pop()
  },
  props: {
    flowId: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      headers: [
        { text: 'Name', value: 'name', width: '20%' },
        { text: 'Mapped', value: 'mapped', width: '10%' },
        { text: 'Max Retries', value: 'max_retries', width: '15%' },
        { text: 'Retry Delay', value: 'retry_delay', width: '15%' },
        { text: 'Class', value: 'type', width: '20%' },
        { text: 'Trigger', value: 'trigger', width: '20%' }
      ],
      itemsPerPage: 15,
      loading: 0,
      page: 1,
      searchTerm: null,
      sortBy: 'name',
      sortDesc: false,
      tasks: null,
      tasksCount: null
    }
  },
  computed: {
    offset() {
      return this.itemsPerPage * (this.page - 1)
    },
    searchFormatted() {
      if (!this.searchTerm) return null
      return `%${this.searchTerm}%`
    }
  },
  apollo: {
    tasks: {
      query: require('@/graphql/Flow/table-tasks.gql'),
      loadingKey: 'loading',
      variables() {
        const orderBy = {}
        orderBy[`${this.sortBy}`] = this.sortDesc ? 'desc' : 'asc'

        return {
          flowId: this.flowId,
          heartbeat: this.heartbeat,
          limit: this.itemsPerPage,
          name: this.searchFormatted,
          offset: this.offset,
          orderBy
        }
      },
      update: data => {
        if (data && data.task) return data.task
        return []
      }
    },
    tasksCount: {
      query: require('@/graphql/Flow/table-tasks-count.gql'),
      loadingKey: 'loading',
      variables() {
        return {
          flowId: this.flowId,
          heartbeat: this.heartbeat,
          name: this.searchFormatted
        }
      },
      update: data => {
        if (data && data.task_aggregate.aggregate.count)
          return data.task_aggregate.aggregate.count
        return null
      }
    }
  }
}
</script>

<template>
  <v-card class="pa-2 mt-2" tile>
    <CardTitle title="Tasks" icon="fiber_manual_record">
      <v-text-field
        slot="action"
        v-model="searchTerm"
        class="task-search"
        dense
        solo
        prepend-inner-icon="search"
        hide-details
      >
      </v-text-field>
    </CardTitle>

    <v-card-text>
      <v-data-table
        v-if="loading === 0"
        :footer-props="{
          'items-per-page-options': [5, 15, 25, 50],
          'prev-icon': 'chevron_left',
          'next-icon': 'chevron_right'
        }"
        :headers="headers"
        :header-props="{ 'sort-icon': 'arrow_drop_up' }"
        :items="tasks"
        :items-per-page.sync="itemsPerPage"
        :loading="loading > 0"
        must-sort
        :page.sync="page"
        :server-items-length="tasksCount"
        :sort-by.sync="sortBy"
        :sort-desc.sync="sortDesc"
      >
        <template v-slot:item.name="{ item }">
          <router-link
            class="link"
            :data-cy="'task-link|' + item.name"
            :to="{ name: 'task', params: { id: item.id } }"
          >
            {{ item.name }}
          </router-link>
        </template>

        <template v-slot:item.mapped="{ item }">
          <v-icon v-if="item.mapped" color="primary">
            check
          </v-icon>
          <span v-else>
            -
          </span>
        </template>

        <template v-slot:item.retry_delay="{ item }">
          <span v-if="item.retry_delay">{{ item.retry_delay | duration }}</span>
          <span v-else>
            -
          </span>
        </template>

        <template v-slot:item.max_retries="{ item }">
          {{ item.max_retries | number }}
        </template>

        <template v-slot:item.type="{ item }">
          {{ item.type | typeClass }}
        </template>

        <template v-slot:item.trigger="{ item }">
          {{ item.trigger | typeClass }}
        </template>
      </v-data-table>

      <div v-else-if="loading > 0">
        <v-skeleton-loader type="table-thead" />
        <v-skeleton-loader type="table-tbody" />
        <v-skeleton-loader type="table-tfoot" />
      </div>
    </v-card-text>
  </v-card>
</template>

<style lang="scss">
.fixed-table {
  table {
    table-layout: fixed;
  }
}

.v-data-table {
  font-size: 0.9rem !important;

  td {
    font-size: inherit !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.pointer {
  cursor: pointer;
}
</style>

<style lang="scss">
.fixed-table {
  table {
    table-layout: fixed;
  }
}

.v-data-table {
  font-size: 0.9rem !important;

  td,
  th {
    font-size: inherit !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .last-ten-runs {
    overflow-x: scroll !important;
  }
}

.task-search {
  border-radius: 0 !important;
  font-size: 0.85rem;

  .v-icon {
    font-size: 20px !important;
  }
}
</style>
