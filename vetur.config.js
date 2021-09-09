// vetur.config.js
/** @type {import('vls').VeturConfig} */
module.exports = {
  settings: {
    "vetur.useWorkspaceDependencies": true,
    "vetur.experimental.templateInterpolationService": true,
  },
  projects: [
    "./ui",
    {
      root: "./ui",
      package: "./package.json",
      tsconfig: "./tsconfig.json",
    },
  ],
};
