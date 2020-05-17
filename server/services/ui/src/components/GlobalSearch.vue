<script>
import globalNameSearchQuery from '@/graphql/GlobalSearch/search-by-name.gql'
import globalIDSearchQuery from '@/graphql/GlobalSearch/search-by-id.gql'
import GlobalSearchIcon from '@/components/GlobalSearchIcon'
import GlobalSearchResult from '@/components/GlobalSearchResult'

export default {
  components: { GlobalSearchIcon, GlobalSearchResult },
  data() {
    return {
      input: null,
      model: null,
      search: null,
      results: [],
      isLoading: false
    }
  },
  computed: {
    id() {
      if (!this.input) return ''

      // Call .trim() to get rid of whitespace on the ends of the
      // string before making the query
      return `${this.input.trim()}`
    },
    isSearchForID() {
      const UUIDRegex = /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/

      // Call .trim() to get rid of whitespace on the ends of the
      // string before making the query
      return UUIDRegex.test(this.input.trim())
    },
    name() {
      if (!this.input) return ''
      // Call .trim() to get rid of whitespace on the ends of the
      // string before making the query
      return `%${this.input.trim()}%`
    },
    entries() {
      return this.results
    }
  },
  watch: {
    search(val) {
      this.handleSearch(val)
    },
    model(val) {
      this.handleResultSelected(val)
    }
  },
  mounted() {
    // Adds the event listener for the / search shortcut
    window.addEventListener('keyup', this.handleKeyboardShortcut)
  },
  beforeDestroy() {
    // Removes the / search shortcut event listener when
    // the component is destroyed
    window.removeEventListener('keyup', this.handleKeyboardShortcut)
  },
  methods: {
    handleKeyboardShortcut(e) {
      if (
        e.key &&
        e.key === '/' &&
        e.srcElement.tagName !== 'INPUT' &&
        e.srcElement.tagName !== 'TEXTAREA'
      ) {
        // We use the .onClick() method here rather than .focus()
        // because .focus() doesn't bring up the context menu
        // .onClick() also calls .focus()
        this.$refs['global-search'].onClick()
      }
    },
    handleSearch(input) {
      // We set the input prop to null if the input
      // string is empty, to bring back up the searchbox hint
      this.input = input == '' ? null : input

      // If there's no input or apollo has been told to
      // pause all queries elsewhere (the skipAll prop),
      // we pause the individual queries and
      // remove all results. This will show the typing hint
      // again if the user has focused the global search focus
      if (!input || this.$apollo.skipAll) {
        this.$apollo.queries.nameQuery.skip = true
        this.$apollo.queries.idQuery.skip = true
        this.results = []
        return
      }

      // Once we've confirmed that we have input and
      // we aren't pausing all queries, we check that
      // the input matches a UUID regex which is stored as
      // a computed prop called isSearchForID
      // If that's the case, we start an id query and
      // pause the name query.
      if (this.isSearchForID) {
        this.startQuery('id')
        this.$apollo.queries.nameQuery.skip = true
      }
      // Otherwise, we start a name query and pause
      // the id query.
      else {
        this.startQuery('name')
        this.$apollo.queries.idQuery.skip = true
      }
    },
    handleResultSelected(searchResultName) {
      // If this is called with no argument
      // we return immediately
      if (!searchResultName) return

      // The search result that we use is found in the
      // entries on name, since the VAutocomplete
      // component will always pass the name prop to this
      // method regardless of the query used (id or name)
      let searchResult = this.entries.find(
        result => result.name == searchResultName
      )

      // Pause all queries
      this.$apollo.skipAll = true

      const routeToNavigateTo = this.routeName(searchResult.__typename)

      // Navigate to the URL based on the search result
      this.$router.push({
        name: routeToNavigateTo,
        params: { id: searchResult.id }
      })
    },
    routeName(name) {
      switch (name) {
        case 'flow':
          return 'flow'
        case 'task':
          return 'task'
        case 'flow_run':
          return 'flow-run'
        case 'task_run':
          return 'task-run'
        default:
          throw new Error('Unable to resolve route, GlobalSearchResult')
      }
    },
    startQuery(ref) {
      this.isLoading = true
      // We make sure to unpause this query before
      // we try to refetch the data
      this.$apollo.queries[`${ref}Query`].skip = false
      this.$apollo.queries[`${ref}Query`].refetch()
    },
    processResult(data, loading) {
      this.isLoading = loading
      // Returning if GraphQL is loading the query still
      // leads to a better UX since the search results
      // don't flicker between loading states
      // i.e. we maintain is loading until GraphQL
      // has determined loading is finished NOT
      // when we've received some data
      if (this.isLoading) return

      this.results = data
        ? Object.entries(data)
            .map(e => e[1].map(e1 => (e1 ? { ...e1 } : [])))
            .flat()
        : []
    },
    searchFilter(item, queryText) {
      // This is the filter we use to determine what the VAutocomplete
      // method is showing. We transform all queries to lowercase
      // for comparison for a better UX
      return (
        item['id'].toLowerCase().includes(queryText.toLowerCase()) ||
        item['name'].toLowerCase().includes(queryText.toLowerCase())
      )
    }
  },
  apollo: {
    idQuery: {
      query: globalIDSearchQuery,
      manual: true,
      debounce: 300,
      fetchPolicy: 'no-cache',
      variables() {
        return { id: this.id }
      },
      result({ data, loading }) {
        this.processResult(data, loading)
      },
      skip: true
    },
    nameQuery: {
      query: globalNameSearchQuery,
      manual: true,
      debounce: 300,
      fetchPolicy: 'no-cache',
      variables() {
        return { name: this.name }
      },
      result({ data, loading }) {
        this.processResult(data, loading)
      },
      skip: true
    }
  }
}
</script>

<template>
  <v-autocomplete
    ref="global-search"
    v-model="model"
    single-line
    dense
    dark
    clearable
    :items="entries"
    :loading="isLoading ? 'green accent-3' : false"
    :search-input.sync="search"
    :filter="searchFilter"
    label="Search"
    placeholder="Search"
    prepend-inner-icon="search"
    item-text="name"
    clear-icon="close"
    open-on-clear
    class="global-search"
    @clear="results = []"
    @focus="
      results = []
      handleSearch(input)
    "
  >
    <template v-if="input == null" v-slot:no-data>
      <v-list-item>
        <v-list-item-title>
          Type to search for a <strong>Flow</strong>, <strong>Task</strong>, or
          <strong>Run</strong>
        </v-list-item-title>
      </v-list-item>
    </template>
    <template v-else-if="isLoading" v-slot:no-data>
      <v-list-item>
        <v-list-item-title>
          Searching...
        </v-list-item-title>
      </v-list-item>
    </template>
    <template v-else v-slot:no-data>
      <v-list-item>
        <v-list-item-title>
          No results matched your search.
        </v-list-item-title>
      </v-list-item>
    </template>
    <template v-slot:item="data">
      <GlobalSearchIcon v-if="data" :type="data.item.__typename" />
      <GlobalSearchResult
        v-if="data"
        :search-result="data.item"
        :parent="data.parent"
      />
    </template>
  </v-autocomplete>
</template>

<style lang="scss" scoped>
$width: 25rem;

.global-search {
  font-size: 1rem;
  height: 2rem;
  max-width: $width;
}

.v-select-list {
  max-width: $width;
}
</style>
