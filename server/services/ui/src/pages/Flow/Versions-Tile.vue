<script>
import CardTitle from '@/components/Card-Title'

export default {
  components: {
    CardTitle
  },
  props: {
    flowId: {
      required: false,
      type: String,
      default: () => null
    },
    version: {
      required: false,
      type: Number,
      default: () => null
    }
  },
  data() {
    return {
      headers: [
        {
          text: '',
          value: 'archived',
          sortable: false,
          width: '5%'
        },
        {
          text: 'Name',
          value: 'name',
          width: '20%'
        },
        {
          text: 'Version',
          value: 'version',
          width: '15%'
        },
        {
          text: 'Created',
          value: 'created',
          width: '25%'
        },
        {
          text: 'Last State',
          value: 'latest_state',
          sortable: false,
          align: 'end',
          width: '15%'
        }
      ],
      itemsPerPage: 15,
      loading: 0,
      searchTerm: null,
      sortBy: 'name',
      sortDesc: false
    }
  },
  computed: {
    offset() {
      return this.itemsPerPage * (this.page - 1)
    },
    searchFormatted() {
      if (!this.searchTerm) return null
      return parseInt(this.searchTerm)
    }
  },
  apollo: {
    versions: {
      query: require('@/graphql/Flow/flow-versions.gql'),
      variables() {
        return {
          flowId: this.flowId,
          search: this.searchFormatted
        }
      },
      loadingKey: 'loading',
      update: data => data?.flow_by_pk?.versions,
      fetchPolicy: 'no-cache'
    }
  }
}
</script>

<template>
  <v-card class="pa-2 mt-2" tile>
    <CardTitle title="Flow Versions" icon="loop">
      <v-text-field
        slot="action"
        v-model="searchTerm"
        class="flow-search"
        dense
        solo
        prepend-inner-icon="search"
        placeholder="Search by Version"
        hide-details
      >
      </v-text-field>
    </CardTitle>

    <v-card-text class="pa-0">
      <v-data-table
        class="ma-2"
        :header-props="{ 'sort-icon': 'arrow_drop_up' }"
        :headers="headers"
        :items="versions"
        :loading="loading > 0"
        must-sort
        :items-per-page.sync="itemsPerPage"
        :footer-props="{
          showFirstLastPage: true,
          itemsPerPageOptions: [5, 15, 25, 50],
          firstIcon: 'first_page',
          lastIcon: 'last_page',
          prevIcon: 'keyboard_arrow_left',
          nextIcon: 'keyboard_arrow_right'
        }"
        :class="{ 'fixed-table': $vuetify.breakpoint.smAndUp }"
        calculate-widths
      >
        <template v-slot:item.name="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <router-link
                class="link"
                :to="{
                  name: 'flow',
                  params: { id: item.id }
                }"
              >
                <span v-on="on">{{ item.name }}</span>
              </router-link>
            </template>
            <span>{{ item.name }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.created="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on">
                {{ item.created | displayDate }}
              </span>
            </template>
            <span>{{ item.created | displayTimeDayMonthYear }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.archived="{ item }">
          <v-tooltip v-if="!item.archived" top>
            <template v-slot:activator="{ on }">
              <v-icon small dark color="green" v-on="on">
                timeline
              </v-icon>
            </template>
            <span>{{ item.archived ? 'Archived' : 'Active' }}</span>
          </v-tooltip>
          <v-tooltip v-else top>
            <template v-slot:activator="{ on }">
              <v-icon small dark color="accent-pink" v-on="on">
                archive
              </v-icon>
            </template>
            <span>{{ item.archived ? 'Archived' : 'Active' }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.latest_state="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <v-icon
                small
                :color="
                  item.flow_runs.length ? item.flow_runs[0].state : 'gray'
                "
                v-on="on"
              >
                brightness_1
              </v-icon>
            </template>
            <span>
              {{ item.flow_runs.length ? item.flow_runs[0].state : 'None' }}
            </span>
          </v-tooltip>
        </template>
      </v-data-table>
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

.pointer {
  cursor: pointer;
}

.flow-search {
  border-radius: 0 !important;
  font-size: 0.85rem;

  .v-icon {
    font-size: 20px !important;
  }
}
</style>
