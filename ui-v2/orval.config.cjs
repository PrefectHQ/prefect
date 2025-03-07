module.exports = {
	prefect: {
		output: {
			client: "zod",
			mode: "tags-split",
			target: "./src/api/zod",
		},
		hooks: {
			afterAllFilesWrite: ["npm run format"],
		},
		input: {
			target: "./oss_schema.json",
			filters: {
				mode: "exclude",
				// See https://github.com/orval-labs/orval/issues/1961
				tags: ["Flow Run Graph"],
			},
		},
	},
};
