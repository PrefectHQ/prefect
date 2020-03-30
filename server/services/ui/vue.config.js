module.exports = {
  chainWebpack: config => {
    config.resolve.symlinks(false)

    config.module
      .rule('flow')
      .test(/\.flow$/)
      .use('ignore-loader')
      .loader('ignore-loader')
      .end()
  },
  pluginOptions: {
    lintStyleOnBuild: true,
    stylelint: {},
    apollo: {
      lintGQL: true
    }
  }
}
