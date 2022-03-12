<template>
  <div class="container" v-click-outside="handleBlur">
    <form id="search-form" class="search-wrapper search-box" role="search">
      <input
        v-model="query"
        id="search-input"
        ref="search"
        class="search-query"
        autocomplete="off"
        @click="showResults = true"
        @focus="showResults = true"
        @keyup="handleKeypress"
      />
    </form>
    <transition name="fade" mode="out-in">
      <div v-show="showResults" class="results">
        <div class="marvin" :class="{ small: query }">
          <img :src="'/assets/marvin.jpg'" alt="Marvin Picture" />
          <transition name="fade">
            <div v-if="!query">
              There's only one life-form as intelligent as me within thirty
              parsecs of here and that's me. What do you want?
            </div>
            <div v-else>
              Fine, I'll use my immense brainpower to search for
              <span class="algolia-docsearch-suggestion--highlight">{{
                query
              }}</span
              >...
              <hr />
            </div>
          </transition>
        </div>

        <div v-if="resultsGroups.length" class="pagination">
          <div class="pages">
            Page {{ page + 1 }} of
            {{ totalPages }}
          </div>

          <div class="buttons">
            <div class="ripple" @click="decrementPage">
              <span class="arrow left"></span>
            </div>
            <div class="ripple" @click="incrementPage">
              <span class="arrow right"></span>
            </div>
          </div>
        </div>

        <div class="query-results-container">
          <li
            v-for="group in resultsGroups"
            :key="group.group"
            class="group-result"
          >
            <div class="group">
              {{ group.category }}
            </div>
            <div class="hits">
              <div
                v-for="r in group.hits"
                :key="r.id"
                class="result-item ripple"
                @click="navigateToResult(r.url)"
                @keyup.enter="navigateToResult(r.url)"
                tabindex="0"
              >
                <div v-html="r.val1" />

                <div
                  v-if="r.val2"
                  class="subtext"
                  v-html="r.isCode ? highlightCode(r.val2) : r.val2"
                />
              </div>
            </div>
          </li>

          <transition name="fade">
            <div v-if="query && !resultsGroups.length" style="padding: 0 25px">
              I couldn't find anything while searching for
              <span class="algolia-docsearch-suggestion--highlight">{{
                query
              }}</span
              >... call that job satisfaction? 'Cos I don't.
            </div>
          </transition>
        </div>
        <div class="results-footer">
          <a
            v-if="query"
            href="https://www.algolia.com/docsearch"
            target="_blank"
          >
            <img :src="'/assets/search-by-algolia-light-background.svg'" />
          </a>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import algoliasearch from 'algoliasearch/dist/algoliasearch.umd.js'
import { unescape } from 'lodash'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import vClickOutside from 'v-click-outside'

hljs.registerLanguage('python', python)

export default {
  name: 'AlgoliaSearchBox',
  props: ['options'],
  directives: {
    clickOutside: vClickOutside.directive
  },
  data() {
    return {
      client: algoliasearch('BH4D9OD16A', '553c75634e1d4f09c84f7a513f9cc4f9'),
      index: null,
      marvinImgSrc: null,
      hitsPerPage: 10,
      page: 0,
      totalPages: 1,
      query: null,
      results: [],
      resultsGroups: [],
      totalResults: 0,
      showResults: false
    }
  },
  watch: {
    $lang(newValue) {
      this.update(newValue)
    }
  },
  mounted() {
    const marvin = new Image()
    marvin.src = '/assets/marvin.jpg'

    this.initialize(this.$lang)
    this.placeholder = this.$site.themeConfig.searchPlaceholder || ''

    // Adds the event listener for the / search shortcut
    window.addEventListener('keyup', this.handleKeyboardShortcut)
  },
  beforeDestroy() {
    // Removes the / search shortcut event listener when
    // the component is destroyed
    window.removeEventListener('keyup', this.handleKeyboardShortcut)
  },
  methods: {
    handleKeypress() {
      this.page = 0
      this.search()
    },
    incrementPage() {
      if (this.page < this.totalPages - 1) {
        this.page++
        this.search()
      }
    },
    decrementPage() {
      if (this.page > 0) {
        this.page--
        this.search()
      }
    },
    handleKeyboardShortcut(e) {
      if (
        e.key &&
        e.key === '/' &&
        e.srcElement.tagName !== 'INPUT' &&
        e.srcElement.tagName !== 'TEXTAREA'
      ) {
        this.$refs['search'].focus()
      }
    },
    async search() {
      if (!this.query) {
        this.results = []
        this.resultsGroups = []
        return
      }

      const results = await this.index.search(this.query, {
        hitsPerPage: this.hitsPerPage,
        page: this.page
      })

      this.totalPages = results.nbPages
      this.totalResults = results.nbHits

      const groups = []
      results.hits.forEach(hit => {
        let category
        if (hit.url) {
          const isCore = hit.url.includes('/core/')
          const isOrchestration = hit.url.includes('/orchestration/')
          const isAPI = hit.url.includes('/api/')
          if (isCore) category = 'Core'
          if (isOrchestration) category = 'Cloud/Server Orchestration'
          if (isAPI) category = 'API Docs'
        }

        let categoryIndex = groups.findIndex(g => g.category == category)

        if (categoryIndex > -1) {
          groups[categoryIndex].hits.push(hit)
        } else {
          groups.push({
            group: hit.hierarchy.lvl0,
            hits: [hit],
            category: category
          })
        }
      })

      groups.forEach(g =>
        g.hits.forEach(hit => {
          let val1, val2, isCode

          Object.keys(hit.hierarchy).forEach(key => {
            if (!hit.hierarchy[key]) return

            if (!val1) {
              val1 = hit._highlightResult.hierarchy[key].value
              return
            }

            if (key == 'lvl6' && !val2) {
              isCode = true
              val2 = hit.hierarchy[key]

              return
            } else if (!val2) {
              val2 = hit._highlightResult.hierarchy[key].value
              return
            }
          })

          hit.val1 = val1
          hit.val2 = val2
          hit.isCode = isCode
        })
      )

      this.results = results.hits
      this.resultsGroups = groups
    },
    navigateToResult(url) {
      const { pathname, hash } = new URL(url)
      const routepath = pathname.replace(this.$site.base, '/')
      const _hash = decodeURIComponent(hash)
      this.$router.push(`${routepath}${_hash}`)
      this.showResults = false
    },
    initialize(lang) {
      this.index = this.client.initIndex('prefect')
    },
    update(lang) {
      this.initialize(lang)
    },
    highlightCode(code) {
      const split = code.split('\n')
      const line = split.find(l => l.includes(this.query))

      if (!line) null

      const decoded = decodeURI(unescape(line))
      const highlightResult = hljs.highlight('python', unescape(decoded))

      if (highlightResult.illegal) return unescape(line)
      return highlightResult.value
    },
    handleBlur() {
      this.showResults = false
    }
  }
}
</script>

<style lang="styl">
.container
  position relative
  outline none
  white-space initial !important
  line-height 1rem !important

.query-results-container
  max-height 60vh
  overflow scroll

.results
  background-color white
  filter: drop-shadow(0px 2px 2px rgba(130,130,130,1))
  position absolute
  padding 5px 10px
  left 1.5rem
  top 3.25rem
  min-width 300px
  max-width 50vw
  width 700px
  z-index 9999

  @media screen and (max-width: 720px) {
    right 1.5rem
    left unset
  }

  &::before
    content ""
    border-right 20px solid transparent
    border-bottom 20px solid white
    position absolute
    top -20px
    left 0
    width 0

    @media screen and (max-width: 720px) {
      border-left 20px solid transparent
      border-right unset
      right 0
      left unset
    }

.group-result
  display grid
  grid-template-columns 100px auto
  line-height  1rem
  margin 10px auto
  padding 5px auto
  user-select none

.group
  border-right 2px solid #27b1ff
  color rgba(0, 0, 0, 0.45)
  padding 10px 10px 10px 0
  text-align right
  white-space initial !important

.hits
  display inline-block

.result-item
  cursor pointer
  overflow hidden
  padding 10px 5px
  text-overflow ellipsis
  white-space nowrap
  max-width 85%
  width 100%
  font-weight 500
  margin 5px 10px

.marvin
  display flex
  align-items center
  transition all 50ms

  img
    border-radius 50%
    border 5px solid #27b1ff
    transition all 150ms
    height 85px


  &.small
    img
      height 50px

  div
    font-weight 500
    line-height 1rem
    padding 0 20px
    white-space initial !important
    width 100%

.subtext
  color rgba(0, 0, 0, 0.45)
  font-size 0.8rem
  font-style italic
  overflow hidden
  text-overflow ellipsis
  white-space nowrap
  width 100%

.results-footer
  justify-content flex-end
  display flex

  img
    max-height 20px


.algolia-docsearch-suggestion--highlight
    padding: 0 !important
    color: #3b8dff !important

.pagination
  display flex
  justify-content flex-end

  .pages
    font-size 0.75rem
    text-align right
    line-height 0.75rem
    margin-top auto
    margin-bottom auto

  .buttons
    display flex

  .buttons div
    display flex
    justify-content center
    align-items center
    border-radius 50%
    cursor pointer
    height 20px
    margin auto 7.5px
    width 20px


.ripple
  background-position center
  transition background 500ms
  &:hover,
  &:active,
  &:focus
    outline unset
    background rgba(133, 146, 158, 0.15) radial-gradient(circle, transparent 1%, rgba(133, 146, 158, 0.05) 1%) center/15000%

  &:active
    background-color rgba(133, 146, 158, 0.05)
    background-size 100%
    transition background 50ms

.hljs
  display block
  overflow-x auto
  color #657b83


.hljs-comment,
.hljs-quote
  display initial !important
  font-style italic
  font-weight 700
  color #a5b4be - 15%
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-comment
  display block !important

.hljs-keyword,
.hljs-selector-tag,
.hljs-addition
  display initial !important
  color #27b1ff
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-number,
.hljs-string,
.hljs-meta .hljs-meta-string,
.hljs-literal,
.hljs-doctag,
.hljs-regexp
  display initial !important
  color #fe5196
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-title,
.hljs-section,
.hljs-name,
.hljs-selector-id,
.hljs-selector-class
  display initial !important
  color #3b8dff
  font-weight 700
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-attribute,
.hljs-attr,
.hljs-variable,
.hljs-template-variable,
.hljs-class .hljs-title,
.hljs-type
  display initial !important
  color #b58900
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-symbol,
.hljs-bullet,
.hljs-subst,
.hljs-meta,
.hljs-meta .hljs-keyword,
.hljs-selector-attr,
.hljs-selector-pseudo,
.hljs-link
  display initial !important
  color #fe5196
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-built_in,
.hljs-deletion
  display initial !important
  color #dc322f
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-formula
  display initial !important
  background #eee8d5
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-emphasis
  display initial !important
  font-style italic
  overflow hidden
  text-overflow ellipsis
  white-space nowrap

.hljs-strong
  display initial !important
  font-weight bold
  overflow hidden
  text-overflow ellipsis
  white-space nowrap
</style>
