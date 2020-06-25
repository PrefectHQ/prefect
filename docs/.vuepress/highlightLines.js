// currently the build-in plugin for highlight-lines is broken
const wrapperRE = /^<pre .*?><code>/

// flat is not available in all backends (netlify)
Object.defineProperty(Array.prototype, 'flat', {
  value: function(depth = 1) {
    return this.reduce(function(flat, toFlatten) {
      return flat.concat(
        Array.isArray(toFlatten) && depth > 1
          ? toFlatten.flat(depth - 1)
          : toFlatten
      )
    }, [])
  }
})

module.exports = md => {
  const fence = md.renderer.rules.fence
  md.renderer.rules.fence = (...args) => {
    const [tokens, idx, options] = args
    const token = tokens[idx]

    if (!token.lineNumbers) {
      if (
        !token.info ||
        !token.attrs ||
        !token.attrs.length ||
        !token.attrs[0].length
      ) {
        return fence(...args)
      }

      let attrs = token.attrs.flat().join('')

      const lineNumbers = attrs
        .split(',')
        .map(v => v.split('-').map(v => parseInt(v, 10)))

      token.lineNumbers = lineNumbers
    }

    const code = options.highlight
      ? options.highlight(token.content, token.info)
      : token.content

    const rawCode = code.replace(wrapperRE, '')
    const highlightLinesCode = rawCode
      .split('\n')
      .map((split, index) => {
        const lineNumber = index + 1
        const inRange = token.lineNumbers.some(([start, end]) => {
          if (start && end) {
            return lineNumber >= start && lineNumber <= end
          }
          return lineNumber === start
        })
        if (inRange) {
          return `<div class="highlighted">&nbsp;</div>`
        }
        return '<br>'
      })
      .join('')

    const highlightLinesWrapperCode = `<div class="highlight-lines">${highlightLinesCode}</div>`

    return `<div class="language-${token.info} extra-class">${highlightLinesWrapperCode}${code}</div>`
  }
}
