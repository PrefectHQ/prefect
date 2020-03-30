module.exports = {
  root: true,
  extends: ['stylelint-config-recommended', 'stylelint-config-sass-guidelines'],
  plugins: ['stylelint-scss', 'stylelint-order', 'stylelint-a11y'],
  rules: {
    'max-nesting-depth': [
      3,
      {
        ignoreAtRules: ['each', 'media', 'supports', 'include']
      }
    ],
    'function-parentheses-space-inside': 'never-single-line',
    'a11y/no-outline-none': true,
    'a11y/selector-pseudo-class-focus': true,
    'a11y/content-property-no-static-value': [true, { severity: 'warning' }],
    'a11y/font-size-is-readable': [true, { severity: 'warning' }],
    'a11y/line-height-is-vertical-rhythmed': [true, { severity: 'warning' }],
    'a11y/no-display-none': [true, { severity: 'warning' }],
    'a11y/no-spread-text': [true, { severity: 'warning' }],
    'a11y/no-obsolete-attribute': [true, { severity: 'warning' }],
    'a11y/no-obsolete-element': [true, { severity: 'warning' }],
    'a11y/no-text-align-justify': [true, { severity: 'warning' }]
  }
}
