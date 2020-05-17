<script>
/* eslint-disable vue/no-v-html */
// Added this line to disable to the v-html
// console warning since we know we can trust the
// data coming from the GraphQL server

import 'babel-polyfill'
import gql from 'graphql-tag'
import { buildClientSchema, isNonNullType } from 'graphql'
import CodeMirror from 'codemirror'
import { codemirror } from 'vue-codemirror'
import 'codemirror/lib/codemirror.css'
import 'codemirror/mode/javascript/javascript'
import 'codemirror/addon/hint/show-hint'
import 'codemirror/addon/display/placeholder'
import 'codemirror/addon/edit/matchbrackets'
import 'codemirror/addon/edit/closebrackets'
import 'codemirror/addon/comment/comment'
import { getAutocompleteSuggestions } from 'graphql-language-service-interface'
import 'codemirror-graphql/hint'
import 'codemirror-graphql/mode'
import Schema from './Schema'
import 'codemirror/addon/search/searchcursor'

import js_beautify from 'js-beautify'

import '@/styles/highlightjs.default.css'
import '@/styles/playground.scss'

export default {
  components: {
    codemirror,
    Schema
  },
  data() {
    return {
      categorySelected: null,
      docSearch: null,
      shortcutModal: false,
      query: this.$route.query.request
        ? decodeURI(this.$route.query.request)
        : '',
      isLoading: false,
      results: '',
      autoCompleteDisplayed: false,
      autoCompletePhrase: null,
      autoCompletePosition: null,
      autoCompleteList: [],
      autoCompleteSelectionIndex: 0,
      schemaItems: [],
      selectedSchema: null,
      lastInput: null,
      limit: 10,
      offset: 0,
      maxResults: 100,
      formattedResults: '',
      editorOptions: null,
      editor: null,
      enterPressed: false,
      rightPanelView: this.$route.query.request ? 'results' : 'docs',
      shortcuts: [
        { command: '⌘ + ⏎', description: 'Send your request' },
        { command: '⌥ + F', description: 'Format text in the editor' },
        {
          command: 'tab',
          description: 'Insert the currently highlighted item'
        },
        {
          command: '⌘ + /',
          description:
            'Comment out the current selection (or line if no selection exists)'
        }
      ],
      queriesWithoutLimits: []
    }
  },
  computed: {
    // Using a computed prop for the editor options
    // because codemirror does NOT like it when
    // the schema options are undefined at first
    resultsOptions() {
      return {
        tabSize: 2,
        theme: 'playground-light',
        mode: 'application/json',
        viewportMargin: Infinity,
        placeholder:
          'Enter your query/mutation in the left panel... your results will display here!',
        readOnly: true,
        lineWrapping: true,
        cursorBlinkRate: -1
      }
    },
    autoCompleteStyle() {
      return {
        display: this.autoCompleteDisplayed ? 'block' : 'none',
        position: 'absolute',
        top: this.autoCompletePosition.top - 35 + 'px',
        left: this.autoCompletePosition.left + 'px',
        'z-index': 5
      }
    }
  },
  watch: {
    query(val) {
      let strippedRequest = encodeURI(val.replace(/\s\s+/g, ' '))

      // This avoids the route vue router duplication console error
      if (strippedRequest == this.$route.query.request) return

      this.$router.replace({
        query: { request: strippedRequest }
      })
    },
    autoCompleteSelectionIndex(index) {
      this.$refs['autocomplete-item'][index].$el.scrollIntoView({
        block: 'nearest',
        behavior: 'auto'
      })
    },
    docSearch(val) {
      if (!val) {
        this.selectedSchema = null
      } else {
        this.filterSchema(val)
      }
    }
  },
  mounted() {
    if (this.$route.query.request) {
      this.query = this.format(this.query.replace(/\s/g, '\n'))
      this.makeApolloCall()
    }
  },
  methods: {
    split(text) {
      if (!text) return
      let start = text.indexOf(this.autoCompletePhrase),
        end = start + this.autoCompletePhrase.length
      if (start < 0) return text
      return `<span class="item-text">${text.slice(
        0,
        start
      )}<span class="highlighted">${this.autoCompletePhrase}</span>${text.slice(
        end,
        text.length
      )}</span>`
    },
    hasSubFields(schema) {
      if (!schema) return false
      return !!(
        schema.type._fields ||
        (schema.type.ofType && schema.type.ofType._fields) ||
        (schema.type.ofType &&
          schema.type.ofType.ofType &&
          schema.type.ofType.ofType._fields) ||
        (schema.type.ofType &&
          schema.type.ofType.ofType &&
          schema.type.ofType.ofType.ofType &&
          schema.type.ofType.ofType.ofType._fields)
      )
    },
    getCurrentSelectionParent() {
      const prevSelection = this.editor.listSelections()[0]
      const cur = this.editor.getCursor()

      let searchCursor = this.editor.getSearchCursor('{', cur)
      searchCursor.findPrevious()

      let range = this.editor.findWordAt({
        line: searchCursor.pos.from.line,
        ch: searchCursor.pos.from.ch - 2
      })

      this.editor.setSelection(range.anchor, range.head)
      let word = this.editor.getSelection()

      this.editor.setSelection(prevSelection.anchor, prevSelection.head)
      return word
    },
    getRequiredArgs(schema) {
      if (!schema || !schema.args) return []
      return schema.args.filter(arg => isNonNullType(arg.type))
    },
    format(input) {
      return js_beautify(input, {
        indent_size: 2,
        space_in_empty_paren: true,
        preserve_newlines: true,
        unformatted: ['#'],
        unformatted_content_delimiter: ['#']
      })
    },
    handleAutoCompleteShortcut(e) {
      if (e.metaKey || !this.autoCompleteDisplayed) return
      this.handleAutoCompleteSelection()
    },
    handleFormatShortcut(e) {
      let cursor = this.editor.doc.getCursor()
      if (e.altKey) {
        this.editor.setValue(this.format(this.query))
        this.editor.doc.setCursor(cursor)
      }
    },
    handleChange(editor, change) {
      this.query = editor.getValue()
      if (change.origin !== 'complete') {
        editor.showHint()
        this.autoCompletePosition = editor.charCoords(change.to)
      }
    },
    handleCursorActivity(editor) {
      this.query = editor.getValue()
      editor.showHint()
      this.autoCompletePosition = editor.cursorCoords()
    },
    handleAutoCompleteSelection() {
      const cur = this.editor.getCursor()
      const token = this.editor.getTokenAt(cur)
      const textToReplace = this.autoCompleteList[
        this.autoCompleteSelectionIndex
      ].text

      let schema = this.schemaItems.find(item => item.name === textToReplace)

      if (!schema) {
        // If no schema was present, we know this is a subfield,
        // so we check one more level down for schema
        let parentFieldName = this.getCurrentSelectionParent()

        let parentSchema = this.schemaItems.find(
          item => item.name === parentFieldName
        )

        if (parentSchema) {
          schema =
            (parentSchema.type._fields &&
              parentSchema.type._fields[textToReplace]) ||
            (parentSchema.type.ofType &&
              parentSchema.type.ofType._fields &&
              parentSchema.type.ofType._fields[textToReplace]) ||
            (parentSchema.type.ofType &&
              parentSchema.type.ofType.ofType &&
              parentSchema.type.ofType.ofType._fields &&
              parentSchema.type.ofType.ofType._fields[textToReplace]) ||
            (parentSchema.type.ofType &&
              parentSchema.type.ofType.ofType &&
              parentSchema.type.ofType.ofType.ofType &&
              parentSchema.type.ofType.ofType.ofType._fields &&
              parentSchema.type.ofType.ofType.ofType._fields[textToReplace])
        }
      }

      let requiredArgs = this.getRequiredArgs(schema)

      let shouldAddBracketsAndIndent =
        this.hasSubFields(schema) ||
        textToReplace == 'mutation' ||
        textToReplace == 'query' ||
        textToReplace == 'fragment'

      if (token.string == '(') {
        this.editor.replaceSelection(
          `${textToReplace}: ${textToReplace == 'input' ? '{}' : '""'}`
        )
        this.editor.execCommand('goCharRight')
        this.editor.replaceSelection(' {')
        this.editor.execCommand('newlineAndIndent')
        this.editor.execCommand('newlineAndIndent')
        this.editor.replaceSelection('}')
        this.editor.execCommand('indentAuto')

        this.editor.execCommand('goLineUp')
        this.editor.execCommand('goLineUp')
        this.editor.execCommand('goLineEnd')
        this.editor.execCommand('goCharLeft')
        this.editor.execCommand('goCharLeft')
        this.editor.execCommand('goCharLeft')
        this.editor.execCommand('goCharLeft')

        return
      }

      if (token.string.includes(',')) {
        this.editor.execCommand('newlineAndIndent')
        cur.line++
      }

      this.editor.replaceRange(
        textToReplace +
          (shouldAddBracketsAndIndent && !requiredArgs.length ? ' ' : ''),
        { line: cur.line, ch: token.start },
        { line: cur.line, ch: token.end }
      )

      if (requiredArgs.length > 0) {
        this.editor.replaceSelection('(')
        requiredArgs.forEach(arg => {
          if (requiredArgs.length > 1)
            this.editor.execCommand('newlineAndIndent')

          // We could replace the double quote autopopulation
          // with a lookup of the GraphQLType if we wanted
          // but what would we put there for non-scalar?
          // Will leave as is for now since it helps the user
          // understand that *something* goes there
          this.editor.replaceSelection(
            `${arg.name}: ${arg.name == 'input' ? '{}' : '""'}`
          )
        })
        this.editor.replaceSelection(') ')
      }

      if (shouldAddBracketsAndIndent) {
        this.editor.replaceSelection('{')
        this.editor.execCommand('newlineAndIndent')
        this.editor.execCommand('newlineAndIndent')
        this.editor.replaceSelection('}')
        this.editor.execCommand('indentAuto')
        this.editor.execCommand('goLineUp')
        this.editor.execCommand('indentAuto')
      } else {
        this.editor.setCursor({
          line: cur.line,
          ch: token.start + textToReplace.length
        })
      }

      this.editor.focus()

      this.closeHint()
    },
    closeHint() {
      this.autoCompleteDisplayed = false
    },
    hint(editor, options) {
      const schema = options.schema

      if (!schema) {
        return
      }

      const cur = editor.getCursor()
      const token = editor.getTokenAt(cur)
      const rawResults = getAutocompleteSuggestions(
        schema,
        editor.getValue(),
        cur,
        token
      )

      const tokenStart =
        token.type !== null && /"|\w/.test(token.string[0])
          ? token.start
          : token.end

      if (token.string == '}' || token.string == '{') {
        this.closeHint()
        return
      }

      const results = {
        list: rawResults
          .filter(item => (token.string !== ')' ? item.label !== '{' : true))
          .map(item => ({
            text: item.label,
            type: schema.getType(item.detail),
            desc: item.documentation
          })),
        from: { line: cur.line, column: tokenStart },
        to: { line: cur.line, column: token.end }
      }

      if (results && results.list && results.list.length > 0) {
        results.from = CodeMirror.Pos(results.from.line, results.from.column)
        results.to = CodeMirror.Pos(results.to.line, results.to.column)
        CodeMirror.signal(editor, 'hasCompletion', editor, results, token)
      }

      this.autoCompletePhrase = token.string
      this.autoCompleteList = results.list
      this.autoCompleteSelectionIndex = 0

      if (results.list.length === 1 && token.string == results.list[0].text) {
        this.autoCompleteDisplayed = false
      } else {
        this.autoCompleteDisplayed =
          token.string.trim() !== '' &&
          results.list.length > 0 &&
          token.string.trim() !== results.list[0].text
      }
    },
    async makeApolloCall() {
      if (!this.query) return
      this.isLoading = true
      this.rightPanelView = 'results'
      this.results = ''

      let gqlObj

      try {
        // This try catch is to enforce the
        // structure of the gql string
        // without trying to send the request
        gqlObj = gql`
          ${this.query}
        `
      } catch (e) {
        this.results = this.format(JSON.stringify(e))
        this.isLoading = false
        return
      }

      let definition =
        gqlObj.definitions && gqlObj.definitions[0]
          ? gqlObj.definitions[0].operation
          : null

      if (definition) {
        // We add this because apollo methods don't match
        // operation definitions (verb/noun diff)
        let method = definition == 'mutation' ? 'mutate' : definition

        gqlObj = definition == 'query' ? this.limitQuery(gqlObj) : gqlObj

        // Using this to tag the request so we can attach a header
        // Note: I have no idea if this is the correct way to do this
        // but the docs aren't giving any hints of a better way so ¯\_(ツ)_/¯
        gqlObj.source = 'InteractiveAPI'
        try {
          let result = await this.$apollo[method]({
            [definition]: gqlObj,
            fetchPolicy: 'no-cache'
          })

          this.results = this.format(JSON.stringify(result.data))
          if (result.error) {
            this.results = this.format(JSON.stringify(result.error))
          }
        } catch (e) {
          this.results = this.format(JSON.stringify(e))
        }
      }
      this.isLoading = false
    },
    limitQuery(gqlObj) {
      gqlObj.definitions[0].selectionSet.selections.forEach(selection => {
        // *_by_pk queries are helper queries that don't have offset and limit
        // arguments since by their nature they return just 1 result using a
        // uuid!
        if (selection.name.value.includes('_by_pk')) return

        // Exclude queries that do not support limiting
        if (this.queriesWithoutLimits.includes(selection.name.value)) return

        let limitArg = {
          kind: 'Argument',
          manual: true,
          name: { kind: 'Name', value: 'limit' },
          value: {
            kind: 'IntValue',
            // This ensures sending the query while still focused on the limit box will actually limit the query
            value:
              +this.limit > 0 && +this.limit <= this.maxResults
                ? this.limit
                : 10
          }
        }

        let offsetArg = {
          kind: 'Argument',
          manual: true,
          name: { kind: 'Name', value: 'offset' },
          value: {
            kind: 'IntValue',
            value: +this.offset > -1 ? +this.offset : 0
          }
        }

        let limitIndex = selection.arguments.findIndex(
          arg => arg.name.value == 'limit'
        )

        if (limitIndex > -1) {
          selection.arguments[limitIndex] = limitArg
        } else {
          selection.arguments.push(limitArg)
        }

        let offsetIndex = selection.arguments.findIndex(
          arg => arg.name.value == 'offset'
        )

        // This check is because of some odd
        // caching in the schema
        if (offsetIndex == -1) {
          selection.arguments[selection.arguments.length] = offsetArg
        } else if (selection.arguments[offsetIndex].manual) {
          selection.arguments[offsetIndex] = offsetArg
        }
      })
      return gqlObj
    },
    configureEditor() {
      // Have to use the regular lib for CodeMirror
      // because vue throws an error
      // when passing in GraphQL schema for some reason
      this.editor = CodeMirror.fromTextArea(
        document.getElementById('gql-editor'),
        this.editorOptions
      )
      this.editor.on('change', this.handleChange)
      this.editor.on('cursorActivity', this.handleCursorActivity)

      this.editor.setOption('extraKeys', {
        Up: editor => {
          if (this.autoCompleteDisplayed) {
            this.autoCompleteSelectionIndex--
            this.autoCompleteSelectionIndex =
              this.autoCompleteSelectionIndex < 0
                ? this.autoCompleteList.length - 1
                : this.autoCompleteSelectionIndex
            return CodeMirror.PASS
          }
          return editor.execCommand('goLineUp')
        },
        Down: editor => {
          if (this.autoCompleteDisplayed) {
            this.autoCompleteSelectionIndex++
            this.autoCompleteSelectionIndex =
              this.autoCompleteSelectionIndex >= this.autoCompleteList.length
                ? 0
                : this.autoCompleteSelectionIndex
            return CodeMirror.PASS
          }
          return editor.execCommand('goLineDown')
        },
        Tab: editor => {
          if (this.autoCompleteDisplayed) {
            return this.handleAutoCompleteSelection()
          }
          return editor.execCommand('indentMore')
        },
        'Shift-Tab': editor => {
          return editor.execCommand('indentLess')
        },
        Enter: editor => {
          if (this.autoCompleteDisplayed && !this.enterPressed) {
            this.enterPressed = true
            return this.handleAutoCompleteSelection()
          }
          this.enterPressed = false
          editor.execCommand('newlineAndIndent')
          return editor.execCommand('indentAuto')
        },
        'Ctrl-/': editor => editor.execCommand('toggleComment'),
        'Cmd-/': editor => editor.execCommand('toggleComment')
      })
    },
    selectCategory(input) {
      if (input == this.categorySelected) {
        this.selectedSchema = null
        this.categorySelected = null
        return
      }
      this.categorySelected = input
      this.selectedSchema = this.schemaItems.filter(si => si.action == input)
    },
    filterSchema() {
      this.categorySelected = null
      this.selectedSchema = this.schemaItems.filter(si => {
        return (
          si.name.includes(this.docSearch) ||
          si.description.includes(this.docSearch)
        )
      })
    },
    selectSchema(input) {
      this.selectedSchema = [this.schemaItems.find(si => si.name == input)]
    },
    // This is added as a method because we don't
    // want to use traditional vuetify validation
    // and display an error to the user but instead
    // fall back to sensible defaults
    validateLimit() {
      let limint = +this.limit
      if (limint >= 1 && limint <= this.maxResults) {
        return
      } else if (limint > this.maxResults) {
        this.limit = this.maxResults
      } else if (limint < 1) {
        this.limit = 1
      } else {
        this.limit = 1
      }
    },
    // This is added as a method because we don't
    // want to use traditional vuetify validation
    // and display an error to the user but instead
    // fall back to sensible defaults
    validateOffset() {
      let offint = +this.offset
      if (offint >= 0) {
        return
      } else if (offint < 0) {
        this.offset = 0
      }
    }
  },

  apollo: {
    introspectionQuery: {
      query: require('@/graphql/Playground/schema.gql'),
      update(data) {
        let schema = buildClientSchema(data)
        // Map schema queries
        let schemaQ = schema._queryType._fields,
          i = 0
        for (let type in schemaQ) {
          this.schemaItems[i] = { ...schemaQ[type], action: 'query' }
          i++
        }

        // Map schema mutations
        let schemaM = schema._mutationType._fields
        for (let type in schemaM) {
          this.schemaItems[i] = { ...schemaM[type], action: 'mutation' }
          i++
        }

        this.editorOptions = {
          autofocus: true,
          tabSize: 2,
          indentUnit: 2,
          theme: 'playground',
          lineNumbers: true,
          lineWrapping: true,
          line: true,
          mode: 'graphql',
          placeholder:
            'Enter your query/mutation here\n\nPress ⌘ + ⏎ or the RUN button to send your request\n ⌥ + F formats the text in the editor\n\n\nHappy Engineering! :^)\n',
          viewportMargin: Infinity,
          hintOptions: {
            schema: schema,
            hint: this.hint
          },
          matchBrackets: true,
          autoCloseBrackets: true
        }
        this.configureEditor()
        return data
      },
      watchLoading(isLoading) {
        this.isLoading = isLoading
      },
      fetchPolicy: 'network-only'
    }
  }
}
</script>

<template>
  <v-container fluid class="pa-0 editors–container">
    <v-row no-gutters style="height: 100%;">
      <v-col cols="12">
        <v-row
          class="area"
          align="stretch"
          justify="center"
          no-gutters
          style="height: 100%;
          overflow: hidden;"
        >
          <v-col
            cols="12"
            md="6"
            class="editor-container"
            @keydown.meta.enter="makeApolloCall"
            @keydown.70="handleFormatShortcut"
            @keydown.esc="closeHint"
          >
            <v-toolbar dense color="#1d252b" dark>
              <v-spacer></v-spacer>

              <v-toolbar-items>
                <div
                  class="mr-3"
                  style="
                  display: inline;
                  height: 48px;
                  line-height: 48px;
                  user-select: none;"
                  >Offset:
                </div>
                <v-text-field
                  v-model="offset"
                  dense
                  hide-details
                  single-line
                  type="number"
                  min="0"
                  style="
                  align-items: center;
                  width: 40px;
                  "
                  @blur="validateOffset"
                ></v-text-field>

                <v-tooltip bottom>
                  <template v-slot:activator="{ on }">
                    <v-icon small v-on="on">
                      info
                    </v-icon>
                  </template>
                  This sets the global page offset for results. Inline query
                  offset arguments are NOT overidden by this value. Defaults to
                  0.
                </v-tooltip>

                <div
                  class="mr-3 ml-10"
                  style="
                  display: inline;
                  height: 48px;
                  line-height: 48px;
                  user-select: none;"
                  >Limit:
                </div>
                <v-text-field
                  v-model="limit"
                  class="ma-0 pa-0"
                  dense
                  hide-details
                  single-line
                  type="number"
                  min="0"
                  :max="maxResults"
                  style="
                  align-items: center;
                  width: 40px;
                  "
                  @blur="validateLimit"
                ></v-text-field>

                <v-tooltip bottom>
                  <template v-slot:activator="{ on }">
                    <v-icon small v-on="on">
                      info
                    </v-icon>
                  </template>
                  This limits the number of results returned by your queries,
                  with a max of 100 results per subquery. Inline query limit
                  arguments are overidden by this value. Defaults to 10.
                </v-tooltip>
              </v-toolbar-items>
            </v-toolbar>

            <v-btn
              absolute
              dark
              class="run-button"
              color="#da2072"
              @click="makeApolloCall"
            >
              Run
            </v-btn>
            <textarea id="gql-editor" v-model="query" class="editor"></textarea>
          </v-col>
          <v-col cols="12" md="6" class="editor-container">
            <v-tabs
              v-model="rightPanelView"
              right
              background-color="#1d252b"
              class="elevation-24"
              dark
            >
              <v-tabs-slider color="accentOrange"></v-tabs-slider>

              <v-tab href="#results">
                Results
              </v-tab>
              <v-tab href="#docs">
                Docs
              </v-tab>
              <v-tab v-if="false" href="#recipes">
                Recipes
              </v-tab>

              <v-tab-item class="iapi-container" value="results">
                <v-container
                  fluid
                  class="pa-4 iapi-container container--results"
                >
                  <v-progress-circular
                    v-if="isLoading"
                    class="loader"
                    indeterminate
                    :size="175"
                    color="light-blue"
                  >
                    Fetching results...
                  </v-progress-circular>
                  <codemirror
                    ref="results"
                    v-model="results"
                    class="editor"
                    :options="resultsOptions"
                  ></codemirror>
                </v-container>
              </v-tab-item>

              <v-tab-item value="docs">
                <v-container fluid class="pa-4 iapi-container container--docs">
                  <transition-group name="doc-instructions">
                    <div
                      v-if="!selectedSchema"
                      key="1"
                      class="text-center my-8 body-2 doc-instructions-item"
                    >
                      You can search through the schema here...
                    </div>
                    <v-text-field
                      key="2"
                      v-model="docSearch"
                      autocomplete="new-password"
                      class="doc-instructions-item"
                      color="accentOrange"
                      dense
                      placeholder="Search the schema"
                      solo
                      single-line
                      style="
                        margin: auto;
                        max-width: 30rem;"
                    />
                    <div
                      v-if="!selectedSchema"
                      key="3"
                      class="text-center my-8 body-2 doc-instructions-item"
                    >
                      ... or view all the schema for a selected type.
                    </div>
                    <div
                      v-if="!docSearch || docSearch == ''"
                      key="4"
                      class="text-center doc-instructions-item"
                    >
                      <v-btn
                        color="codeBlue"
                        text
                        large
                        :style="{
                          color: categorySelected == 'query' ? '#fff' : '',
                          backgroundColor:
                            categorySelected == 'query'
                              ? 'rgba(0, 115, 223, 0.25)'
                              : ''
                        }"
                        @click="selectCategory('query')"
                      >
                        Queries
                      </v-btn>
                      <v-btn
                        color="codePink"
                        text
                        large
                        :style="{
                          color: categorySelected == 'mutation' ? '#fff' : '',
                          backgroundColor:
                            categorySelected == 'mutation'
                              ? 'rgba(218, 32, 114, 0.25)'
                              : ''
                        }"
                        @click="selectCategory('mutation')"
                      >
                        Mutations
                      </v-btn>
                    </div>

                    <Schema
                      v-if="selectedSchema"
                      key="5"
                      class="doc-instructions-item"
                      :schema="selectedSchema"
                      @select-schema="selectSchema"
                    />
                  </transition-group>
                  <div
                    v-if="!selectedSchema"
                    class="text-center my-8 body-2 doc-instructions-item"
                  >
                    For GraphQL examples, please see our
                    <a
                      href="https://docs.prefect.io/orchestration/ui/interactive-api.html"
                      target="_blank"
                      >Interactive API docs.
                    </a>
                  </div>
                </v-container>
              </v-tab-item>

              <v-tab-item value="recipes">
                <v-container
                  fluid
                  class="pa-4 iapi-container container--recipes"
                >
                  This is where I'd put recipes if I had them!
                </v-container>
              </v-tab-item>
            </v-tabs>
          </v-col>
        </v-row>
      </v-col>
    </v-row>
    <v-btn
      absolute
      x-small
      light
      fab
      class="shortcut-button"
      color="#edf0f3"
      @click="shortcutModal = true"
    >
      <v-icon>more_vert</v-icon>
    </v-btn>

    <v-dialog v-model="shortcutModal" width="400">
      <v-card>
        <v-card-title class="headline" primary-title>
          Shortcuts
        </v-card-title>

        <v-card-text>
          <v-row
            v-for="(shortcut, index) in shortcuts"
            :key="index"
            class="my-5 d-flex justify-space-between"
            no-gutters
          >
            <v-col class="body-1 shortcut-command">
              {{ shortcut.command }}
            </v-col>
            <v-col class="body-2">{{ shortcut.description }}</v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-list
      v-if="autoCompleteList.length"
      two-line
      dense
      :style="autoCompleteStyle"
      max-height="300"
      class="autocomplete-popup elevation-3"
    >
      <v-list-item
        v-for="(ac, index) in autoCompleteList"
        ref="autocomplete-item"
        :key="index"
        dense
        ripple
        class="autocomplete-item"
        :class="index == autoCompleteSelectionIndex ? 'selected' : ''"
        @mouseover="autoCompleteSelectionIndex = index"
        @click="handleAutoCompleteSelection"
      >
        <v-list-item-content>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <v-list-item-title v-html="split(ac.text)"></v-list-item-title>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <v-list-item-subtitle v-html="split(ac.desc)"></v-list-item-subtitle>
        </v-list-item-content>
      </v-list-item>
    </v-list>
  </v-container>
</template>

<style lang="scss">
.autocomplete-popup {
  border-radius: 0;
  max-height: 200px;
  overflow-y: scroll;
  width: 300px;

  .autocomplete-item {
    cursor: pointer;

    .highlighted {
      color: #da2072;
    }

    &.selected {
      background-color: #d6d5d4;

      .item-text {
        color: #1d252b;
      }
    }
  }

  .v-select-list {
    margin: auto;
    max-width: 30rem;
  }

  /* stylelint-disable selector-class-pattern */
  .v-list-item__mask {
    background-color: rgba(247, 112, 98, 0.5) !important;
    color: #000 !important;
    padding: 0 1px !important;
  }
}

.results {
  height: 100%;
  overflow: hidden;
}

.run-button {
  bottom: 25px;
  right: 25px;
  z-index: 4;
}

.shortcut-button {
  bottom: 25px;
  left: 25px;
  z-index: 4;
}

.editor-container {
  bottom: 0;
  height: calc(100vh - 64px);
  left: 0;
  overflow: hidden;
  position: relative;
  top: 0;
}

.iapi-container {
  background: #edf0f3;
  height: calc(100vh - 64px - 48px); /* Adjust 270px to suits your needs */
  overflow-y: auto;
}

.editor {
  height: 100%;
  overflow-y: scroll;
}

.editors-container {
  height: 100%;
}

.shortcut-command {
  color: #0075b8;
}

.loader {
  left: 50%;
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 4;
}

.doc-instructions-item {
  transition: transform 250ms, opacity 200ms;
}

.doc-instructions-enter,
.doc-instructions-leave-to {
  opacity: 0;
  transform: translateX(-300px);
}

.doc-instructions-leave-active {
  position: absolute;
}

.v-text-field input {
  padding: 0 !important;
}
</style>
