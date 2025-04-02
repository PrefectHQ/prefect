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
				mode: "include",
				tags: ["Events"],
			},
		},
	},
};
