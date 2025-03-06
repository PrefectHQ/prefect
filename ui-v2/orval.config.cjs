module.exports = {
	prefect: {
		output: {
			client: "zod",
			mode: "tags-split",
			target: "./src/api/zod",
		},
		input: {
			target: "./oss_schema.json",
			filters: {
				mode: "exclude",
				tags: ["Flow Run Graph"],
			},
		},
	},
};
