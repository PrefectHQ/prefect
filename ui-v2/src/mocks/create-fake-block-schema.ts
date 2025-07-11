import { rand } from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const BLOCK_SCHEMAS: Array<components["schemas"]["BlockSchema"]> = [
	{
		id: "b8694d73-57a9-40c9-aa9c-524d92bcc6ce",
		created: "2024-12-02T18:19:08.226282Z",
		updated: "2024-12-02T18:19:08.226283Z",
		checksum:
			"sha256:01e6c0bdaac125860811b201f5a5e98ffefd5f8a49f1398b6996aec362643acc",
		fields: {
			title: "SqlAlchemyConnector",
			description:
				"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost.",
			type: "object",
			properties: {
				connection_info: {
					title: "Connection Info",
					description:
						"SQLAlchemy URL to create the engine; either create from components or create from a string.",
					anyOf: [
						{
							$ref: "#/definitions/ConnectionComponents",
						},
						{
							type: "string",
							minLength: 1,
							maxLength: 65536,
							format: "uri",
						},
					],
				},
				connect_args: {
					title: "Additional Connection Arguments",
					description:
						"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
					type: "object",
				},
				fetch_size: {
					title: "Fetch Size",
					description: "The number of rows to fetch at a time.",
					default: 1,
					type: "integer",
				},
			},
			required: ["connection_info"],
			block_type_slug: "sqlalchemy-connector",
			secret_fields: ["connection_info.password"],
			definitions: {
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "c840a999-050f-462a-a9a5-cf09b4a10d3d",
		block_type: {
			id: "c840a999-050f-462a-a9a5-cf09b4a10d3d",
			created: "2024-12-02T18:19:08.071111Z",
			updated: "2024-12-02T18:19:08.071112Z",
			name: "SQLAlchemy Connector",
			slug: "sqlalchemy-connector",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/3c7dff04f70aaf4528e184a3b028f9e40b98d68c-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-sqlalchemy/database/#prefect_sqlalchemy.database.SqlAlchemyConnector",
			description:
				"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost. This block is part of the prefect-sqlalchemy collection. Install prefect-sqlalchemy with `pip install prefect-sqlalchemy` to use this block.",
			code_example:
				'Load stored database credentials and use in context manager:\n```python\nfrom prefect_sqlalchemy import SqlAlchemyConnector\n\ndatabase_block = SqlAlchemyConnector.load("BLOCK_NAME")\nwith database_block:\n    ...\n```\n\nCreate table named customers and insert values; then fetch the first 10 rows.\n```python\nfrom prefect_sqlalchemy import (\n    SqlAlchemyConnector, SyncDriver, ConnectionComponents\n)\n\nwith SqlAlchemyConnector(\n    connection_info=ConnectionComponents(\n        driver=SyncDriver.SQLITE_PYSQLITE,\n        database="prefect.db"\n    )\n) as database:\n    database.execute(\n        "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);",\n    )\n    for i in range(1, 42):\n        database.execute(\n            "INSERT INTO customers (name, address) VALUES (:name, :address);",\n            parameters={"name": "Marvin", "address": f"Highway {i}"},\n        )\n    results = database.fetch_many(\n        "SELECT * FROM customers WHERE name = :name;",\n        parameters={"name": "Marvin"},\n        size=10\n    )\nprint(results)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.0",
	},
	{
		id: "13d4c4e7-5d62-4f18-9acc-59f2b11eaef1",
		created: "2024-12-02T18:19:08.224084Z",
		updated: "2024-12-02T18:19:08.224086Z",
		checksum:
			"sha256:76d1ccbf0ab2038fea77e9689b91a7c8b6398e080e95d9303f65a93a4c03162e",
		fields: {
			title: "DatabaseCredentials",
			description: "Block used to manage authentication with a database.",
			type: "object",
			properties: {
				driver: {
					title: "Driver",
					description: "The driver name to use.",
					anyOf: [
						{
							$ref: "#/definitions/AsyncDriver",
						},
						{
							$ref: "#/definitions/SyncDriver",
						},
						{
							type: "string",
						},
					],
				},
				username: {
					title: "Username",
					description: "The user name used to authenticate.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				database: {
					title: "Database",
					description: "The name of the database to use.",
					type: "string",
				},
				host: {
					title: "Host",
					description: "The host address of the database.",
					type: "string",
				},
				port: {
					title: "Port",
					description: "The port to connect to the database.",
					type: "string",
				},
				query: {
					title: "Query",
					description:
						"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
					type: "object",
					additionalProperties: {
						type: "string",
					},
				},
				url: {
					title: "Url",
					description:
						"Manually create and provide a URL to create the engine, this is useful for external dialects, e.g. Snowflake, because some of the params, such as 'warehouse', is not directly supported in the vanilla `sqlalchemy.engine.URL.create` method; do not provide this alongside with other URL params as it will raise a `ValueError`.",
					minLength: 1,
					maxLength: 65536,
					format: "uri",
					type: "string",
				},
				connect_args: {
					title: "Connect Args",
					description:
						"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
					type: "object",
				},
			},
			block_type_slug: "database-credentials",
			secret_fields: ["password"],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "075671b0-2a76-47a6-96b6-a7963711acfe",
		block_type: {
			id: "075671b0-2a76-47a6-96b6-a7963711acfe",
			created: "2024-12-02T18:19:08.070452Z",
			updated: "2024-12-02T18:19:08.070453Z",
			name: "Database Credentials",
			slug: "database-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/fb3f4debabcda1c5a3aeea4f5b3f94c28845e23e-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-sqlalchemy/credentials/#prefect_sqlalchemy.credentials.DatabaseCredentials",
			description:
				"Block used to manage authentication with a database. This block is part of the prefect-sqlalchemy collection. Install prefect-sqlalchemy with `pip install prefect-sqlalchemy` to use this block.",
			code_example:
				'Load stored database credentials:\n```python\nfrom prefect_sqlalchemy import DatabaseCredentials\ndatabase_block = DatabaseCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.0",
	},
	{
		id: "c1482b18-5dd1-47c1-930e-b8dfd81e60db",
		created: "2024-12-02T18:19:08.221879Z",
		updated: "2024-12-02T18:19:08.221880Z",
		checksum:
			"sha256:b24edfb413527c951cb2a8b4b4c16aec096523f871d941889e29ac2e6e92e036",
		fields: {
			title: "SnowflakeCredentials",
			description: "Block used to manage authentication with Snowflake.",
			type: "object",
			properties: {
				account: {
					title: "Account",
					description: "The snowflake account name.",
					example: "nh12345.us-east-2.aws",
					type: "string",
				},
				user: {
					title: "User",
					description: "The user name used to authenticate.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				private_key: {
					title: "Private Key",
					description: "The PEM used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				private_key_path: {
					title: "Private Key Path",
					description: "The path to the private key.",
					type: "string",
					format: "path",
				},
				private_key_passphrase: {
					title: "Private Key Passphrase",
					description: "The password to use for the private key.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				authenticator: {
					title: "Authenticator",
					description:
						"The type of authenticator to use for initializing connection.",
					default: "snowflake",
					enum: [
						"snowflake",
						"snowflake_jwt",
						"externalbrowser",
						"okta_endpoint",
						"oauth",
						"username_password_mfa",
					],
					type: "string",
				},
				token: {
					title: "Token",
					description:
						"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				endpoint: {
					title: "Endpoint",
					description:
						"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
					type: "string",
				},
				role: {
					title: "Role",
					description: "The name of the default role to use.",
					type: "string",
				},
				autocommit: {
					title: "Autocommit",
					description: "Whether to automatically commit.",
					type: "boolean",
				},
			},
			required: ["account", "user"],
			block_type_slug: "snowflake-credentials",
			secret_fields: [
				"password",
				"private_key",
				"private_key_passphrase",
				"token",
			],
			block_schema_references: {},
		},
		block_type_id: "6751e26c-5068-40ef-8473-347d71a08e57",
		block_type: {
			id: "6751e26c-5068-40ef-8473-347d71a08e57",
			created: "2024-12-02T18:19:08.069749Z",
			updated: "2024-12-02T18:19:08.069750Z",
			name: "Snowflake Credentials",
			slug: "snowflake-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-snowflake/credentials/#prefect_snowflake.credentials.SnowflakeCredentials",
			description:
				"Block used to manage authentication with Snowflake. This block is part of the prefect-snowflake collection. Install prefect-snowflake with `pip install prefect-snowflake` to use this block.",
			code_example:
				'Load stored Snowflake credentials:\n```python\nfrom prefect_snowflake import SnowflakeCredentials\n\nsnowflake_credentials_block = SnowflakeCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.27.3",
	},
	{
		id: "e26a8050-4bad-47e4-98d1-e2a91711cdbe",
		created: "2024-12-02T18:19:08.217951Z",
		updated: "2024-12-02T18:19:08.217952Z",
		checksum:
			"sha256:dd0d36d69bbe0d44870fd754f3c00754e37e3f52209590083eaee4c585ce0bd0",
		fields: {
			title: "SnowflakeConnector",
			description: "Perform data operations against a Snowflake database.",
			type: "object",
			properties: {
				credentials: {
					title: "Credentials",
					description: "The credentials to authenticate with Snowflake.",
					allOf: [
						{
							$ref: "#/definitions/SnowflakeCredentials",
						},
					],
				},
				database: {
					title: "Database",
					description: "The name of the default database to use.",
					type: "string",
				},
				warehouse: {
					title: "Warehouse",
					description: "The name of the default warehouse to use.",
					type: "string",
				},
				schema: {
					title: "Schema",
					description: "The name of the default schema to use.",
					type: "string",
				},
				fetch_size: {
					title: "Fetch Size",
					description: "The default number of rows to fetch at a time.",
					default: 1,
					type: "integer",
				},
				poll_frequency_s: {
					title: "Poll Frequency [seconds]",
					description:
						"The number of seconds between checking query status for long running queries.",
					default: 1,
					type: "integer",
				},
			},
			required: ["credentials", "database", "warehouse", "schema"],
			block_type_slug: "snowflake-connector",
			secret_fields: [
				"credentials.password",
				"credentials.private_key",
				"credentials.private_key_passphrase",
				"credentials.token",
			],
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:b24edfb413527c951cb2a8b4b4c16aec096523f871d941889e29ac2e6e92e036",
					block_type_slug: "snowflake-credentials",
				},
			},
			definitions: {
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "854376a0-5920-4f44-9cdb-644e342e4618",
		block_type: {
			id: "854376a0-5920-4f44-9cdb-644e342e4618",
			created: "2024-12-02T18:19:08.069093Z",
			updated: "2024-12-02T18:19:08.069094Z",
			name: "Snowflake Connector",
			slug: "snowflake-connector",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-snowflake/database/#prefect_snowflake.database.SnowflakeConnector",
			description:
				"Perform data operations against a Snowflake database. This block is part of the prefect-snowflake collection. Install prefect-snowflake with `pip install prefect-snowflake` to use this block.",
			code_example:
				'Load stored Snowflake connector as a context manager:\n```python\nfrom prefect_snowflake.database import SnowflakeConnector\n\nsnowflake_connector = SnowflakeConnector.load("BLOCK_NAME"):\n```\n\nInsert data into database and fetch results.\n```python\nfrom prefect_snowflake.database import SnowflakeConnector\n\nwith SnowflakeConnector.load("BLOCK_NAME") as conn:\n    conn.execute(\n        "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"\n    )\n    conn.execute_many(\n        "INSERT INTO customers (name, address) VALUES (%(name)s, %(address)s);",\n        seq_of_parameters=[\n            {"name": "Ford", "address": "Highway 42"},\n            {"name": "Unknown", "address": "Space"},\n            {"name": "Me", "address": "Myway 88"},\n        ],\n    )\n    results = conn.fetch_all(\n        "SELECT * FROM customers WHERE address = %(address)s",\n        parameters={"address": "Space"}\n    )\n    print(results)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.27.3",
	},
	{
		id: "bec5b3e0-9e4b-4abf-bebf-bdaf7ee83e35",
		created: "2024-12-02T18:19:08.215843Z",
		updated: "2024-12-02T18:19:08.215845Z",
		checksum:
			"sha256:f79058d8fcf22ed575f824b27daa68a52fedaa0e40f7a8a542d4ac9cf3ee8317",
		fields: {
			title: "SlackCredentials",
			description:
				"Block holding Slack credentials for use in tasks and flows.",
			type: "object",
			properties: {
				token: {
					title: "Token",
					description:
						"Bot user OAuth token for the Slack app used to perform actions.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
			},
			required: ["token"],
			block_type_slug: "slack-credentials",
			secret_fields: ["token"],
			block_schema_references: {},
		},
		block_type_id: "53869ee9-ecb5-41e1-9ee7-b4e89531787e",
		block_type: {
			id: "53869ee9-ecb5-41e1-9ee7-b4e89531787e",
			created: "2024-12-02T18:19:08.068428Z",
			updated: "2024-12-02T18:19:08.068430Z",
			name: "Slack Credentials",
			slug: "slack-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/c1965ecbf8704ee1ea20d77786de9a41ce1087d1-500x500.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-slack/credentials/#prefect_slack.credentials.SlackCredentials",
			description:
				"Block holding Slack credentials for use in tasks and flows. This block is part of the prefect-slack collection. Install prefect-slack with `pip install prefect-slack` to use this block.",
			code_example:
				'Load stored Slack credentials:\n```python\nfrom prefect_slack import SlackCredentials\nslack_credentials_block = SlackCredentials.load("BLOCK_NAME")\n```\n\nGet a Slack client:\n```python\nfrom prefect_slack import SlackCredentials\nslack_credentials_block = SlackCredentials.load("BLOCK_NAME")\nclient = slack_credentials_block.get_client()\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.2.2",
	},
	{
		id: "0fc0edac-8d13-43c0-bf05-5a0c67dd52af",
		created: "2024-12-02T18:19:08.213760Z",
		updated: "2024-12-02T18:19:08.213762Z",
		checksum:
			"sha256:9525e2fd40af302916ff7a4c33ec9c0e20d8970b09243ca010d729fac144811d",
		fields: {
			title: "ShellOperation",
			description:
				"A block representing a shell operation, containing multiple commands.\n\nFor long-lasting operations, use the trigger method and utilize the block as a\ncontext manager for automatic closure of processes when context is exited.\nIf not, manually call the close method to close processes.\n\nFor short-lasting operations, use the run method. Context is automatically managed\nwith this method.",
			type: "object",
			properties: {
				commands: {
					title: "Commands",
					description: "A list of commands to execute sequentially.",
					type: "array",
					items: {
						type: "string",
					},
				},
				stream_output: {
					title: "Stream Output",
					description: "Whether to stream output.",
					default: true,
					type: "boolean",
				},
				env: {
					title: "Environment Variables",
					description: "Environment variables to use for the subprocess.",
					type: "object",
					additionalProperties: {
						type: "string",
					},
				},
				working_dir: {
					title: "Working Directory",
					description:
						"The absolute path to the working directory the command will be executed within.",
					format: "directory-path",
					type: "string",
				},
				shell: {
					title: "Shell",
					description:
						"The shell to run the command with; if unset, defaults to `powershell` on Windows and `bash` on other platforms.",
					type: "string",
				},
				extension: {
					title: "Extension",
					description:
						"The extension to use for the temporary file; if unset, defaults to `.ps1` on Windows and `.sh` on other platforms.",
					type: "string",
				},
			},
			required: ["commands"],
			block_type_slug: "shell-operation",
			secret_fields: [],
			block_schema_references: {},
		},
		block_type_id: "87870e51-71f1-43e1-88d7-35fad79c8c4f",
		block_type: {
			id: "87870e51-71f1-43e1-88d7-35fad79c8c4f",
			created: "2024-12-02T18:19:08.067732Z",
			updated: "2024-12-02T18:19:08.067734Z",
			name: "Shell Operation",
			slug: "shell-operation",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/0b47a017e1b40381de770c17647c49cdf6388d1c-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-shell/commands/#prefect_shell.commands.ShellOperation",
			description:
				"A block representing a shell operation, containing multiple commands.\n\nFor long-lasting operations, use the trigger method and utilize the block as a\ncontext manager for automatic closure of processes when context is exited.\nIf not, manually call the close method to close processes.\n\nFor short-lasting operations, use the run method. Context is automatically managed\nwith this method. This block is part of the prefect-shell collection. Install prefect-shell with `pip install prefect-shell` to use this block.",
			code_example:
				'Load a configured block:\n```python\nfrom prefect_shell import ShellOperation\n\nshell_operation = ShellOperation.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.2.2",
	},
	{
		id: "a586a649-fecf-48ac-a8d3-a4cba258139e",
		created: "2024-12-02T18:19:08.209762Z",
		updated: "2024-12-02T18:19:08.209763Z",
		checksum:
			"sha256:957fa8dca90bd1b5fb9c575ee09e80b454116c0b134287fbc2eff47a72564c3b",
		fields: {
			title: "KubernetesCredentials",
			description:
				"Credentials block for generating configured Kubernetes API clients.",
			type: "object",
			properties: {
				cluster_config: {
					$ref: "#/definitions/KubernetesClusterConfig",
				},
			},
			block_type_slug: "kubernetes-credentials",
			secret_fields: [],
			block_schema_references: {
				cluster_config: {
					block_schema_checksum:
						"sha256:90d421e948bfbe4cdc98b124995f0edd0f84b0837549ad1390423bad8e31cf3b",
					block_type_slug: "kubernetes-cluster-config",
				},
			},
			definitions: {
				KubernetesClusterConfig: {
					title: "KubernetesClusterConfig",
					description:
						"Stores configuration for interaction with Kubernetes clusters.\n\nSee `from_file` for creation.",
					type: "object",
					properties: {
						config: {
							title: "Config",
							description: "The entire contents of a kubectl config file.",
							type: "object",
						},
						context_name: {
							title: "Context Name",
							description: "The name of the kubectl context to use.",
							type: "string",
						},
					},
					required: ["config", "context_name"],
					block_type_slug: "kubernetes-cluster-config",
					secret_fields: [],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "2b92d1f5-3c29-4430-9654-87f052955014",
		block_type: {
			id: "2b92d1f5-3c29-4430-9654-87f052955014",
			created: "2024-12-02T18:19:08.067036Z",
			updated: "2024-12-02T18:19:08.067037Z",
			name: "Kubernetes Credentials",
			slug: "kubernetes-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-kubernetes/credentials/#prefect_kubernetes.credentials.KubernetesCredentials",
			description:
				"Credentials block for generating configured Kubernetes API clients. This block is part of the prefect-kubernetes collection. Install prefect-kubernetes with `pip install prefect-kubernetes` to use this block.",
			code_example:
				'Load stored Kubernetes credentials:\n```python\nfrom prefect_kubernetes.credentials import KubernetesCredentials\n\nkubernetes_credentials = KubernetesCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.3.7",
	},
	{
		id: "958da8a0-6385-47dc-96c7-8acb2b7b07c1",
		created: "2024-12-02T18:19:08.207311Z",
		updated: "2024-12-02T18:19:08.207313Z",
		checksum:
			"sha256:90d421e948bfbe4cdc98b124995f0edd0f84b0837549ad1390423bad8e31cf3b",
		fields: {
			title: "KubernetesClusterConfig",
			description:
				"Stores configuration for interaction with Kubernetes clusters.\n\nSee `from_file` for creation.",
			type: "object",
			properties: {
				config: {
					title: "Config",
					description: "The entire contents of a kubectl config file.",
					type: "object",
				},
				context_name: {
					title: "Context Name",
					description: "The name of the kubectl context to use.",
					type: "string",
				},
			},
			required: ["config", "context_name"],
			block_type_slug: "kubernetes-cluster-config",
			secret_fields: [],
			block_schema_references: {},
		},
		block_type_id: "5471cdd2-2d11-40fd-aa58-897deecf6280",
		block_type: {
			id: "5471cdd2-2d11-40fd-aa58-897deecf6280",
			created: "2024-12-02T18:19:08.066359Z",
			updated: "2024-12-02T18:19:08.066360Z",
			name: "Kubernetes Cluster Config",
			slug: "kubernetes-cluster-config",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png",
			documentation_url:
				"https://docs.prefect.io/api-ref/prefect/blocks/kubernetes/#prefect.blocks.kubernetes.KubernetesClusterConfig",
			description:
				"Stores configuration for interaction with Kubernetes clusters.\n\nSee `from_file` for creation.",
			code_example:
				'Load a saved Kubernetes cluster config:\n```python\nfrom prefect.blocks.kubernetes import KubernetesClusterConfig\n\ncluster_config_block = KubernetesClusterConfig.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.0",
	},
	{
		id: "9f44f06c-f919-4f69-ae5c-40bd1a097656",
		created: "2024-12-02T18:19:08.203385Z",
		updated: "2024-12-02T18:19:08.203387Z",
		checksum:
			"sha256:ac874a97e2ff2403a4b63181b6ae85dd51b4a0df0337d290d922627f5123af44",
		fields: {
			title: "GitLabRepository",
			description: "Interact with files stored in GitLab repositories.",
			type: "object",
			properties: {
				repository: {
					title: "Repository",
					description:
						"The URL of a GitLab repository to read from, in either HTTP/HTTPS or SSH format.",
					type: "string",
				},
				reference: {
					title: "Reference",
					description:
						"An optional reference to pin to; can be a branch name or tag.",
					type: "string",
				},
				credentials: {
					title: "Credentials",
					description:
						"An optional GitLab Credentials block for authenticating with private GitLab repos.",
					allOf: [
						{
							$ref: "#/definitions/GitLabCredentials",
						},
					],
				},
			},
			required: ["repository"],
			block_type_slug: "gitlab-repository",
			secret_fields: ["credentials.token"],
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:7d8d6317127bc66afe9e97ae5658ee8e1decdc598350eb292fb62be379f0246c",
					block_type_slug: "gitlab-credentials",
				},
			},
			definitions: {
				GitLabCredentials: {
					title: "GitLabCredentials",
					description:
						"Store a GitLab personal access token to interact with private GitLab\nrepositories.",
					type: "object",
					properties: {
						token: {
							title: "Token",
							description:
								"A GitLab Personal Access Token with read_repository scope.",
							name: "Personal Access Token",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						url: {
							title: "URL",
							description: "URL to self-hosted GitLab instances.",
							type: "string",
						},
					},
					block_type_slug: "gitlab-credentials",
					secret_fields: ["token"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "4c181281-efdc-454b-adbb-287e04bca8e4",
		block_type: {
			id: "4c181281-efdc-454b-adbb-287e04bca8e4",
			created: "2024-12-02T18:19:08.065679Z",
			updated: "2024-12-02T18:19:08.065681Z",
			name: "GitLab Repository",
			slug: "gitlab-repository",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/a5db0f07a1bb4390f0e1cda9f7ef9091d89633b9-250x250.png",
			documentation_url: null,
			description:
				"Interact with files stored in GitLab repositories. This block is part of the prefect-gitlab collection. Install prefect-gitlab with `pip install prefect-gitlab` to use this block.",
			code_example:
				'```python\nfrom prefect_gitlab.repositories import GitLabRepository\n\ngitlab_repository_block = GitLabRepository.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["get-directory"],
		version: "0.2.2",
	},
	{
		id: "fc657643-8559-4593-980e-c2fd3176c2b8",
		created: "2024-12-02T18:19:08.201290Z",
		updated: "2024-12-02T18:19:08.201291Z",
		checksum:
			"sha256:7d8d6317127bc66afe9e97ae5658ee8e1decdc598350eb292fb62be379f0246c",
		fields: {
			title: "GitLabCredentials",
			description:
				"Store a GitLab personal access token to interact with private GitLab\nrepositories.",
			type: "object",
			properties: {
				token: {
					title: "Token",
					description:
						"A GitLab Personal Access Token with read_repository scope.",
					name: "Personal Access Token",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				url: {
					title: "URL",
					description: "URL to self-hosted GitLab instances.",
					type: "string",
				},
			},
			block_type_slug: "gitlab-credentials",
			secret_fields: ["token"],
			block_schema_references: {},
		},
		block_type_id: "3a28aca0-f3b7-43bf-adff-433231b2c7ef",
		block_type: {
			id: "3a28aca0-f3b7-43bf-adff-433231b2c7ef",
			created: "2024-12-02T18:19:08.064970Z",
			updated: "2024-12-02T18:19:08.064972Z",
			name: "GitLab Credentials",
			slug: "gitlab-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/a5db0f07a1bb4390f0e1cda9f7ef9091d89633b9-250x250.png",
			documentation_url: null,
			description:
				"Store a GitLab personal access token to interact with private GitLab\nrepositories. This block is part of the prefect-gitlab collection. Install prefect-gitlab with `pip install prefect-gitlab` to use this block.",
			code_example:
				'Load stored GitLab credentials:\n```python\nfrom prefect_gitlab import GitLabCredentials\ngitlab_credentials_block = GitLabCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.2.2",
	},
	{
		id: "f1a730f0-f167-4905-905c-4c9a13bf4e96",
		created: "2024-12-02T18:19:08.197281Z",
		updated: "2024-12-02T18:19:08.197282Z",
		checksum:
			"sha256:3d2b2de1cd9336264ccc73f7078264d9053dc956941136516e18050c9953abf0",
		fields: {
			title: "GitHubRepository",
			description: "Interact with files stored on GitHub repositories.",
			type: "object",
			properties: {
				repository_url: {
					title: "Repository URL",
					description:
						"The URL of a GitHub repository to read from, in either HTTPS or SSH format. If you are using a private repo, it must be in the HTTPS format.",
					type: "string",
				},
				reference: {
					title: "Reference",
					description:
						"An optional reference to pin to; can be a branch name or tag.",
					type: "string",
				},
				credentials: {
					title: "Credentials",
					description:
						"An optional GitHubCredentials block for using private GitHub repos.",
					allOf: [
						{
							$ref: "#/definitions/GitHubCredentials",
						},
					],
				},
			},
			required: ["repository_url"],
			block_type_slug: "github-repository",
			secret_fields: ["credentials.token"],
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:74a34b668838ba661d9160ab127053dd44a22dd04e89562839645791e70d046a",
					block_type_slug: "github-credentials",
				},
			},
			definitions: {
				GitHubCredentials: {
					title: "GitHubCredentials",
					description: "Block used to manage GitHub authentication.",
					type: "object",
					properties: {
						token: {
							title: "Token",
							description: "A GitHub personal access token (PAT).",
							type: "string",
							writeOnly: true,
							format: "password",
						},
					},
					block_type_slug: "github-credentials",
					secret_fields: ["token"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "c37dfa45-c748-4c8d-a9f5-53f7d8183117",
		block_type: {
			id: "c37dfa45-c748-4c8d-a9f5-53f7d8183117",
			created: "2024-12-02T18:19:08.064265Z",
			updated: "2024-12-02T18:19:08.064266Z",
			name: "GitHub Repository",
			slug: "github-repository",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/41971cfecfea5f79ff334164f06ecb34d1038dd4-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-github/repository/#prefect_github.repository.GitHubRepository",
			description:
				"Interact with files stored on GitHub repositories. This block is part of the prefect-github collection. Install prefect-github with `pip install prefect-github` to use this block.",
			code_example:
				'```python\nfrom prefect_github.repository import GitHubRepository\n\ngithub_repository_block = GitHubRepository.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["get-directory"],
		version: "0.2.2",
	},
	{
		id: "acff233c-d1b7-4c94-9e63-fc8b99175e89",
		created: "2024-12-02T18:19:08.195175Z",
		updated: "2024-12-02T18:19:08.195177Z",
		checksum:
			"sha256:74a34b668838ba661d9160ab127053dd44a22dd04e89562839645791e70d046a",
		fields: {
			title: "GitHubCredentials",
			description: "Block used to manage GitHub authentication.",
			type: "object",
			properties: {
				token: {
					title: "Token",
					description: "A GitHub personal access token (PAT).",
					type: "string",
					writeOnly: true,
					format: "password",
				},
			},
			block_type_slug: "github-credentials",
			secret_fields: ["token"],
			block_schema_references: {},
		},
		block_type_id: "cfa4cf84-2ace-43b5-a066-3ef26ac739b6",
		block_type: {
			id: "cfa4cf84-2ace-43b5-a066-3ef26ac739b6",
			created: "2024-12-02T18:19:08.063583Z",
			updated: "2024-12-02T18:19:08.063584Z",
			name: "GitHub Credentials",
			slug: "github-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/41971cfecfea5f79ff334164f06ecb34d1038dd4-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-github/credentials/#prefect_github.credentials.GitHubCredentials",
			description:
				"Block used to manage GitHub authentication. This block is part of the prefect-github collection. Install prefect-github with `pip install prefect-github` to use this block.",
			code_example:
				'Load stored GitHub credentials:\n```python\nfrom prefect_github import GitHubCredentials\ngithub_credentials_block = GitHubCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.2.2",
	},
	{
		id: "8b04f562-39f7-4ab7-940d-a2fd5d3b7620",
		created: "2024-12-02T18:19:08.191238Z",
		updated: "2024-12-02T18:19:08.191240Z",
		checksum:
			"sha256:6f44cdbd523fb8d4029fbc504a89095d67d27439aec09d2c1871b03a1f4e14e9",
		fields: {
			title: "GcsBucket",
			description:
				"Block used to store data using GCP Cloud Storage Buckets.\n\nNote! `GcsBucket` in `prefect-gcp` is a unique block, separate from `GCS`\nin core Prefect. `GcsBucket` does not use `gcsfs` under the hood,\ninstead using the `google-cloud-storage` package, and offers more configuration\nand functionality.",
			type: "object",
			properties: {
				bucket: {
					title: "Bucket",
					description: "Name of the bucket.",
					type: "string",
				},
				gcp_credentials: {
					title: "Gcp Credentials",
					description: "The credentials to authenticate with GCP.",
					allOf: [
						{
							$ref: "#/definitions/GcpCredentials",
						},
					],
				},
				bucket_folder: {
					title: "Bucket Folder",
					description:
						"A default path to a folder within the GCS bucket to use for reading and writing objects.",
					default: "",
					type: "string",
				},
			},
			required: ["bucket"],
			block_type_slug: "gcs-bucket",
			secret_fields: ["gcp_credentials.service_account_info.*"],
			block_schema_references: {
				gcp_credentials: {
					block_schema_checksum:
						"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
					block_type_slug: "gcp-credentials",
				},
			},
			definitions: {
				GcpCredentials: {
					title: "GcpCredentials",
					description:
						"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
					type: "object",
					properties: {
						service_account_file: {
							title: "Service Account File",
							description: "Path to the service account JSON keyfile.",
							type: "string",
							format: "path",
						},
						service_account_info: {
							title: "Service Account Info",
							description: "The contents of the keyfile as a dict.",
							type: "object",
						},
						project: {
							title: "Project",
							description: "The GCP project to use for the client.",
							type: "string",
						},
					},
					block_type_slug: "gcp-credentials",
					secret_fields: ["service_account_info.*"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "b50dfffe-a78a-46ee-8578-f3346b76c593",
		block_type: {
			id: "b50dfffe-a78a-46ee-8578-f3346b76c593",
			created: "2024-12-02T18:19:08.062886Z",
			updated: "2024-12-02T18:19:08.062888Z",
			name: "GCS Bucket",
			slug: "gcs-bucket",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-gcp/cloud_storage/#prefect_gcp.cloud_storage.GcsBucket",
			description:
				"Block used to store data using GCP Cloud Storage Buckets.\n\nNote! `GcsBucket` in `prefect-gcp` is a unique block, separate from `GCS`\nin core Prefect. `GcsBucket` does not use `gcsfs` under the hood,\ninstead using the `google-cloud-storage` package, and offers more configuration\nand functionality. This block is part of the prefect-gcp collection. Install prefect-gcp with `pip install prefect-gcp` to use this block.",
			code_example:
				'Load stored GCP Cloud Storage Bucket:\n```python\nfrom prefect_gcp.cloud_storage import GcsBucket\ngcp_cloud_storage_bucket_block = GcsBucket.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["get-directory", "put-directory", "read-path", "write-path"],
		version: "0.5.8",
	},
	{
		id: "5393d48d-2070-4f1c-bd9a-de5273faca97",
		created: "2024-12-02T18:19:08.187161Z",
		updated: "2024-12-02T18:19:08.187163Z",
		checksum:
			"sha256:0311dc4cd2480a4af70d3b30ecd14d296243e73e7245ba064b753e4c0b25acdf",
		fields: {
			title: "GcpSecret",
			description:
				"Manages a secret in Google Cloud Platform's Secret Manager.",
			type: "object",
			properties: {
				gcp_credentials: {
					$ref: "#/definitions/GcpCredentials",
				},
				secret_name: {
					title: "Secret Name",
					description: "Name of the secret to manage.",
					type: "string",
				},
				secret_version: {
					title: "Secret Version",
					description: "Version number of the secret to use.",
					default: "latest",
					type: "string",
				},
			},
			required: ["gcp_credentials", "secret_name"],
			block_type_slug: "gcpsecret",
			secret_fields: ["gcp_credentials.service_account_info.*"],
			block_schema_references: {
				gcp_credentials: {
					block_schema_checksum:
						"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
					block_type_slug: "gcp-credentials",
				},
			},
			definitions: {
				GcpCredentials: {
					title: "GcpCredentials",
					description:
						"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
					type: "object",
					properties: {
						service_account_file: {
							title: "Service Account File",
							description: "Path to the service account JSON keyfile.",
							type: "string",
							format: "path",
						},
						service_account_info: {
							title: "Service Account Info",
							description: "The contents of the keyfile as a dict.",
							type: "object",
						},
						project: {
							title: "Project",
							description: "The GCP project to use for the client.",
							type: "string",
						},
					},
					block_type_slug: "gcp-credentials",
					secret_fields: ["service_account_info.*"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "adb286d8-6ccd-4512-b52d-eb0999c6aac3",
		block_type: {
			id: "adb286d8-6ccd-4512-b52d-eb0999c6aac3",
			created: "2024-12-02T18:19:08.062176Z",
			updated: "2024-12-02T18:19:08.062178Z",
			name: "GcpSecret",
			slug: "gcpsecret",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-gcp/secret_manager/#prefect_gcp.secret_manager.GcpSecret",
			description:
				"Manages a secret in Google Cloud Platform's Secret Manager. This block is part of the prefect-gcp collection. Install prefect-gcp with `pip install prefect-gcp` to use this block.",
			code_example:
				'```python\nfrom prefect_gcp.secret_manager import GcpSecret\n\ngcpsecret_block = GcpSecret.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.5.8",
	},
	{
		id: "c744e116-f3a0-45dc-9cbf-91aae7adc933",
		created: "2024-12-02T18:19:08.185029Z",
		updated: "2024-12-02T18:19:08.185031Z",
		checksum:
			"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
		fields: {
			title: "GcpCredentials",
			description:
				"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
			type: "object",
			properties: {
				service_account_file: {
					title: "Service Account File",
					description: "Path to the service account JSON keyfile.",
					type: "string",
					format: "path",
				},
				service_account_info: {
					title: "Service Account Info",
					description: "The contents of the keyfile as a dict.",
					type: "object",
				},
				project: {
					title: "Project",
					description: "The GCP project to use for the client.",
					type: "string",
				},
			},
			block_type_slug: "gcp-credentials",
			secret_fields: ["service_account_info.*"],
			block_schema_references: {},
		},
		block_type_id: "a4119249-25c7-45e1-8bf7-4d36114ac4f1",
		block_type: {
			id: "a4119249-25c7-45e1-8bf7-4d36114ac4f1",
			created: "2024-12-02T18:19:08.061455Z",
			updated: "2024-12-02T18:19:08.061456Z",
			name: "GCP Credentials",
			slug: "gcp-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-gcp/credentials/#prefect_gcp.credentials.GcpCredentials",
			description:
				"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns. This block is part of the prefect-gcp collection. Install prefect-gcp with `pip install prefect-gcp` to use this block.",
			code_example:
				'Load GCP credentials stored in a `GCP Credentials` Block:\n```python\nfrom prefect_gcp import GcpCredentials\ngcp_credentials_block = GcpCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.5.8",
	},
	{
		id: "cf20ead9-7f26-4150-bcef-10f26a8924b3",
		created: "2024-12-02T18:19:08.181063Z",
		updated: "2024-12-02T18:19:08.181065Z",
		checksum:
			"sha256:e8495199f3b490e3b15ba1bc67a97cf04b23aa8a7cba67161291d7cbc882d025",
		fields: {
			title: "BigQueryWarehouse",
			description:
				"A block for querying a database with BigQuery.\n\nUpon instantiating, a connection to BigQuery is established\nand maintained for the life of the object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the connection and its cursors when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost.",
			type: "object",
			properties: {
				gcp_credentials: {
					$ref: "#/definitions/GcpCredentials",
				},
				fetch_size: {
					title: "Fetch Size",
					description: "The number of rows to fetch at a time.",
					default: 1,
					type: "integer",
				},
			},
			required: ["gcp_credentials"],
			block_type_slug: "bigquery-warehouse",
			secret_fields: ["gcp_credentials.service_account_info.*"],
			block_schema_references: {
				gcp_credentials: {
					block_schema_checksum:
						"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
					block_type_slug: "gcp-credentials",
				},
			},
			definitions: {
				GcpCredentials: {
					title: "GcpCredentials",
					description:
						"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
					type: "object",
					properties: {
						service_account_file: {
							title: "Service Account File",
							description: "Path to the service account JSON keyfile.",
							type: "string",
							format: "path",
						},
						service_account_info: {
							title: "Service Account Info",
							description: "The contents of the keyfile as a dict.",
							type: "object",
						},
						project: {
							title: "Project",
							description: "The GCP project to use for the client.",
							type: "string",
						},
					},
					block_type_slug: "gcp-credentials",
					secret_fields: ["service_account_info.*"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "763ea87c-fa43-41bd-b4af-dad71255c488",
		block_type: {
			id: "763ea87c-fa43-41bd-b4af-dad71255c488",
			created: "2024-12-02T18:19:08.060762Z",
			updated: "2024-12-02T18:19:08.060763Z",
			name: "BigQuery Warehouse",
			slug: "bigquery-warehouse",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-gcp/bigquery/#prefect_gcp.bigquery.BigQueryWarehouse",
			description:
				"A block for querying a database with BigQuery.\n\nUpon instantiating, a connection to BigQuery is established\nand maintained for the life of the object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the connection and its cursors when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost. This block is part of the prefect-gcp collection. Install prefect-gcp with `pip install prefect-gcp` to use this block.",
			code_example:
				'```python\nfrom prefect_gcp.bigquery import BigQueryWarehouse\n\nbigquery_warehouse_block = BigQueryWarehouse.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.5.8",
	},
	{
		id: "a1272ba6-e2c5-47c6-835f-e690188ea395",
		created: "2024-12-02T18:19:08.178908Z",
		updated: "2024-12-02T18:19:08.178910Z",
		checksum:
			"sha256:56d6491f4b2d4aaae5ce604652416f44d0c8fa39ca68c5f747aee7cb518a41d0",
		fields: {
			title: "EmailServerCredentials",
			description:
				"Block used to manage generic email server authentication.\nIt is recommended you use a\n[Google App Password](https://support.google.com/accounts/answer/185833)\nif you use Gmail.",
			type: "object",
			properties: {
				username: {
					title: "Username",
					description:
						"The username to use for authentication to the server. Unnecessary if SMTP login is not required.",
					type: "string",
				},
				password: {
					title: "Password",
					description:
						"The password to use for authentication to the server. Unnecessary if SMTP login is not required.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				smtp_server: {
					title: "SMTP Server",
					description:
						"Either the hostname of the SMTP server, or one of the keys from the built-in SMTPServer Enum members, like 'gmail'.",
					default: "smtp.gmail.com",
					anyOf: [
						{
							$ref: "#/definitions/SMTPServer",
						},
						{
							type: "string",
						},
					],
				},
				smtp_type: {
					title: "SMTP Type",
					description: "Either 'SSL', 'STARTTLS', or 'INSECURE'.",
					default: 465,
					anyOf: [
						{
							$ref: "#/definitions/SMTPType",
						},
						{
							type: "string",
						},
					],
				},
				smtp_port: {
					title: "SMTP Port",
					description:
						"If provided, overrides the smtp_type's default port number.",
					type: "integer",
				},
			},
			block_type_slug: "email-server-credentials",
			secret_fields: ["password"],
			definitions: {
				SMTPServer: {
					title: "SMTPServer",
					description: "Server used to send email.",
					enum: [
						"smtp.aol.com",
						"smtp.mail.att.net",
						"smtp.comcast.net",
						"smtp.mail.me.com",
						"smtp.gmail.com",
						"smtp-mail.outlook.com",
						"smtp.mail.yahoo.com",
					],
				},
				SMTPType: {
					title: "SMTPType",
					description: "Protocols used to secure email transmissions.",
					enum: [465, 587, 25],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "692436bd-3fb6-41ae-89d1-9899ed362038",
		block_type: {
			id: "692436bd-3fb6-41ae-89d1-9899ed362038",
			created: "2024-12-02T18:19:08.060066Z",
			updated: "2024-12-02T18:19:08.060067Z",
			name: "Email Server Credentials",
			slug: "email-server-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/82bc6ed16ca42a2252a5512c72233a253b8a58eb-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-email/credentials/#prefect_email.credentials.EmailServerCredentials",
			description:
				"Block used to manage generic email server authentication.\nIt is recommended you use a\n[Google App Password](https://support.google.com/accounts/answer/185833)\nif you use Gmail. This block is part of the prefect-email collection. Install prefect-email with `pip install prefect-email` to use this block.",
			code_example:
				'Load stored email server credentials:\n```python\nfrom prefect_email import EmailServerCredentials\nemail_credentials_block = EmailServerCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.3.2",
	},
	{
		id: "449c7003-6bc4-407b-a28f-7641bc38e0c0",
		created: "2024-12-02T18:19:08.176384Z",
		updated: "2024-12-02T18:19:08.176385Z",
		checksum:
			"sha256:d5cbcfdf092e1f904ea26c274fcd0f23d86ecbbd0afae0f254f575ac3e40915d",
		fields: {
			title: "DockerRegistryCredentials",
			description: "Store credentials for interacting with a Docker Registry.",
			type: "object",
			properties: {
				username: {
					title: "Username",
					description: "The username to log into the registry with.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password to log into the registry with.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				registry_url: {
					title: "Registry Url",
					description:
						'The URL to the registry. Generally, "http" or "https" can be omitted.',
					example: "index.docker.io",
					type: "string",
				},
				reauth: {
					title: "Reauth",
					description: "Whether or not to reauthenticate on each interaction.",
					default: true,
					type: "boolean",
				},
			},
			required: ["username", "password", "registry_url"],
			block_type_slug: "docker-registry-credentials",
			secret_fields: ["password"],
			block_schema_references: {},
		},
		block_type_id: "b6d60542-d430-4f9f-b2b0-ff039549dce4",
		block_type: {
			id: "b6d60542-d430-4f9f-b2b0-ff039549dce4",
			created: "2024-12-02T18:19:08.059435Z",
			updated: "2024-12-02T18:19:08.059436Z",
			name: "Docker Registry Credentials",
			slug: "docker-registry-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/14a315b79990200db7341e42553e23650b34bb96-250x250.png",
			documentation_url: null,
			description:
				"Store credentials for interacting with a Docker Registry. This block is part of the prefect-docker collection. Install prefect-docker with `pip install prefect-docker` to use this block.",
			code_example:
				'Log into Docker Registry.\n```python\nfrom prefect_docker import DockerHost, DockerRegistryCredentials\n\ndocker_host = DockerHost()\ndocker_registry_credentials = DockerRegistryCredentials(\n    username="my_username",\n    password="my_password",\n    registry_url="registry.hub.docker.com",\n)\nwith docker_host.get_client() as client:\n    docker_registry_credentials.login(client)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.5",
	},
	{
		id: "4733e201-ddc1-4a5b-b51b-669d0d510997",
		created: "2024-12-02T18:19:08.174285Z",
		updated: "2024-12-02T18:19:08.174287Z",
		checksum:
			"sha256:bf0961e9f2d88fd81bca2c7b78c025bd289776ad84ae8ef22d8f3db8b9561478",
		fields: {
			title: "DockerHost",
			description: "Store settings for interacting with a Docker host.",
			type: "object",
			properties: {
				base_url: {
					title: "Base URL",
					description: "URL to the Docker host.",
					example: "unix:///var/run/docker.sock",
					type: "string",
				},
				version: {
					title: "Version",
					description: "The version of the API to use",
					default: "auto",
					type: "string",
				},
				timeout: {
					title: "Timeout",
					description: "Default timeout for API calls, in seconds.",
					type: "integer",
				},
				max_pool_size: {
					title: "Max Pool Size",
					description: "The maximum number of connections to save in the pool.",
					type: "integer",
				},
				client_kwargs: {
					title: "Additional Configuration",
					description:
						"Additional keyword arguments to pass to `docker.from_env()` or `DockerClient`.",
					type: "object",
				},
			},
			block_type_slug: "docker-host",
			secret_fields: [],
			block_schema_references: {},
		},
		block_type_id: "583708d0-0a67-491d-8e3c-741d0429673c",
		block_type: {
			id: "583708d0-0a67-491d-8e3c-741d0429673c",
			created: "2024-12-02T18:19:08.058763Z",
			updated: "2024-12-02T18:19:08.058765Z",
			name: "Docker Host",
			slug: "docker-host",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/14a315b79990200db7341e42553e23650b34bb96-250x250.png",
			documentation_url: null,
			description:
				"Store settings for interacting with a Docker host. This block is part of the prefect-docker collection. Install prefect-docker with `pip install prefect-docker` to use this block.",
			code_example:
				'Get a Docker Host client.\n```python\nfrom prefect_docker import DockerHost\n\ndocker_host = DockerHost(\nbase_url="tcp://127.0.0.1:1234",\n    max_pool_size=4\n)\nwith docker_host.get_client() as client:\n    ... # Use the client for Docker operations\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.5",
	},
	{
		id: "b4da140a-0f68-4623-a268-0140ba603950",
		created: "2024-12-02T18:19:08.169504Z",
		updated: "2024-12-02T18:19:08.169506Z",
		checksum:
			"sha256:0f685bc693353f66d1fc83687c8af67511feba052b5343506033141c9a2441c7",
		fields: {
			title: "DbtCoreOperation",
			description:
				"A block representing a dbt operation, containing multiple dbt and shell commands.\n\nFor long-lasting operations, use the trigger method and utilize the block as a\ncontext manager for automatic closure of processes when context is exited.\nIf not, manually call the close method to close processes.\n\nFor short-lasting operations, use the run method. Context is automatically managed\nwith this method.",
			type: "object",
			properties: {
				commands: {
					title: "Commands",
					description: "A list of commands to execute sequentially.",
					type: "array",
					items: {
						type: "string",
					},
				},
				stream_output: {
					title: "Stream Output",
					description: "Whether to stream output.",
					default: true,
					type: "boolean",
				},
				env: {
					title: "Environment Variables",
					description: "Environment variables to use for the subprocess.",
					type: "object",
					additionalProperties: {
						type: "string",
					},
				},
				working_dir: {
					title: "Working Directory",
					description:
						"The absolute path to the working directory the command will be executed within.",
					format: "directory-path",
					type: "string",
				},
				shell: {
					title: "Shell",
					description:
						"The shell to run the command with; if unset, defaults to `powershell` on Windows and `bash` on other platforms.",
					type: "string",
				},
				extension: {
					title: "Extension",
					description:
						"The extension to use for the temporary file; if unset, defaults to `.ps1` on Windows and `.sh` on other platforms.",
					type: "string",
				},
				profiles_dir: {
					title: "Profiles Dir",
					description:
						"The directory to search for the profiles.yml file. Setting this appends the `--profiles-dir` option to the dbt commands provided. If this is not set, will try using the DBT_PROFILES_DIR environment variable, but if that's also not set, will use the default directory `$HOME/.dbt/`.",
					type: "string",
					format: "path",
				},
				project_dir: {
					title: "Project Dir",
					description:
						"The directory to search for the dbt_project.yml file. Default is the current working directory and its parents.",
					type: "string",
					format: "path",
				},
				overwrite_profiles: {
					title: "Overwrite Profiles",
					description:
						"Whether the existing profiles.yml file under profiles_dir should be overwritten with a new profile.",
					default: false,
					type: "boolean",
				},
				dbt_cli_profile: {
					title: "Dbt Cli Profile",
					description:
						"Profiles class containing the profile written to profiles.yml. Note! This is optional and will raise an error if profiles.yml already exists under profile_dir and overwrite_profiles is set to False.",
					allOf: [
						{
							$ref: "#/definitions/DbtCliProfile",
						},
					],
				},
			},
			required: ["commands"],
			block_type_slug: "dbt-core-operation",
			secret_fields: [
				"dbt_cli_profile.target_configs.connector.credentials.password",
				"dbt_cli_profile.target_configs.connector.credentials.private_key",
				"dbt_cli_profile.target_configs.connector.credentials.private_key_passphrase",
				"dbt_cli_profile.target_configs.connector.credentials.token",
				"dbt_cli_profile.target_configs.credentials.service_account_info.*",
				"dbt_cli_profile.target_configs.credentials.connection_info.password",
				"dbt_cli_profile.target_configs.credentials.password",
			],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				DbtCliProfile: {
					title: "DbtCliProfile",
					description: "Profile for use across dbt CLI tasks and flows.",
					type: "object",
					properties: {
						name: {
							title: "Name",
							description: "Profile name used for populating profiles.yml.",
							type: "string",
						},
						target: {
							title: "Target",
							description: "The default target your dbt project will use.",
							type: "string",
						},
						target_configs: {
							title: "Target Configs",
							description:
								"Target configs contain credentials and settings, specific to the warehouse you're connecting to.",
							anyOf: [
								{
									$ref: "#/definitions/SnowflakeTargetConfigs",
								},
								{
									$ref: "#/definitions/BigQueryTargetConfigs",
								},
								{
									$ref: "#/definitions/PostgresTargetConfigs",
								},
								{
									$ref: "#/definitions/TargetConfigs",
								},
							],
						},
						global_configs: {
							title: "Global Configs",
							description:
								"Global configs control things like the visual output of logs, the manner in which dbt parses your project, and what to do when dbt finds a version mismatch or a failing model.",
							allOf: [
								{
									$ref: "#/definitions/GlobalConfigs",
								},
							],
						},
					},
					required: ["name", "target", "target_configs"],
					block_type_slug: "dbt-cli-profile",
					secret_fields: [
						"target_configs.connector.credentials.password",
						"target_configs.connector.credentials.private_key",
						"target_configs.connector.credentials.private_key_passphrase",
						"target_configs.connector.credentials.token",
						"target_configs.credentials.service_account_info.*",
						"target_configs.credentials.connection_info.password",
						"target_configs.credentials.password",
					],
					block_schema_references: {
						target_configs: [
							{
								block_schema_checksum:
									"sha256:842c5dc7d4d1557eedff36982eafeda7b0803915942f72224a7f627efdbe5ff5",
								block_type_slug: "dbt-cli-bigquery-target-configs",
							},
							{
								block_schema_checksum:
									"sha256:1552a2d5c102961df4082329f39c10b8a51e26ee687148efd6d71ce8be8850c0",
								block_type_slug: "dbt-cli-postgres-target-configs",
							},
							{
								block_schema_checksum:
									"sha256:a70fca75226dc280c38ab0dda3679d3b0ffdee21af4463f3fb1ad6278405e370",
								block_type_slug: "dbt-cli-snowflake-target-configs",
							},
							{
								block_schema_checksum:
									"sha256:d0c8411280a2529a973b70fb86142959008aad2fe3844c63ab03190e232f776a",
								block_type_slug: "dbt-cli-target-configs",
							},
						],
						global_configs: {
							block_schema_checksum:
								"sha256:63df9d18a1aafde1cc8330cd49f81f6600b4ce6db92955973bbf341cc86e916d",
							block_type_slug: "dbt-cli-global-configs",
						},
					},
				},
				BigQueryTargetConfigs: {
					title: "BigQueryTargetConfigs",
					description:
						"dbt CLI target configs containing credentials and settings, specific to BigQuery.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The type of target.",
							default: "bigquery",
							enum: ["bigquery"],
							type: "string",
						},
						schema: {
							title: "Schema",
							description:
								"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
						project: {
							title: "Project",
							description: "The project to use.",
							type: "string",
						},
						credentials: {
							title: "Credentials",
							description: "The credentials to use to authenticate.",
							allOf: [
								{
									$ref: "#/definitions/GcpCredentials",
								},
							],
						},
					},
					required: ["schema"],
					block_type_slug: "dbt-cli-bigquery-target-configs",
					secret_fields: ["credentials.service_account_info.*"],
					block_schema_references: {
						credentials: {
							block_schema_checksum:
								"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
							block_type_slug: "gcp-credentials",
						},
					},
				},
				GcpCredentials: {
					title: "GcpCredentials",
					description:
						"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
					type: "object",
					properties: {
						service_account_file: {
							title: "Service Account File",
							description: "Path to the service account JSON keyfile.",
							type: "string",
							format: "path",
						},
						service_account_info: {
							title: "Service Account Info",
							description: "The contents of the keyfile as a dict.",
							type: "object",
						},
						project: {
							title: "Project",
							description: "The GCP project to use for the client.",
							type: "string",
						},
					},
					block_type_slug: "gcp-credentials",
					secret_fields: ["service_account_info.*"],
					block_schema_references: {},
				},
				PostgresTargetConfigs: {
					title: "PostgresTargetConfigs",
					description:
						"dbt CLI target configs containing credentials and settings specific to Postgres.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The type of the target.",
							default: "postgres",
							enum: ["postgres"],
							type: "string",
						},
						schema: {
							title: "Schema",
							description:
								"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
						credentials: {
							title: "Credentials",
							description:
								"The credentials to use to authenticate; if there are duplicate keys between credentials and TargetConfigs, e.g. schema, an error will be raised.",
							anyOf: [
								{
									$ref: "#/definitions/SqlAlchemyConnector",
								},
								{
									$ref: "#/definitions/DatabaseCredentials",
								},
							],
						},
					},
					required: ["schema", "credentials"],
					block_type_slug: "dbt-cli-postgres-target-configs",
					secret_fields: [
						"credentials.connection_info.password",
						"credentials.password",
					],
					block_schema_references: {
						credentials: [
							{
								block_schema_checksum:
									"sha256:01e6c0bdaac125860811b201f5a5e98ffefd5f8a49f1398b6996aec362643acc",
								block_type_slug: "sqlalchemy-connector",
							},
							{
								block_schema_checksum:
									"sha256:64175f83f2ae15bef7893a4d9a02658f2b5288747d54594ca6d356dc42e9993c",
								block_type_slug: "database-credentials",
							},
						],
					},
				},
				SqlAlchemyConnector: {
					title: "SqlAlchemyConnector",
					description:
						"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost.",
					type: "object",
					properties: {
						connection_info: {
							title: "Connection Info",
							description:
								"SQLAlchemy URL to create the engine; either create from components or create from a string.",
							anyOf: [
								{
									$ref: "#/definitions/ConnectionComponents",
								},
								{
									type: "string",
									minLength: 1,
									maxLength: 65536,
									format: "uri",
								},
							],
						},
						connect_args: {
							title: "Additional Connection Arguments",
							description:
								"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
							type: "object",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
					},
					required: ["connection_info"],
					block_type_slug: "sqlalchemy-connector",
					secret_fields: ["connection_info.password"],
					block_schema_references: {},
				},
				DatabaseCredentials: {
					title: "DatabaseCredentials",
					description: "Block used to manage authentication with a database.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
						url: {
							title: "Url",
							description:
								"Manually create and provide a URL to create the engine, this is useful for external dialects, e.g. Snowflake, because some of the params, such as 'warehouse', is not directly supported in the vanilla `sqlalchemy.engine.URL.create` method; do not provide this alongside with other URL params as it will raise a `ValueError`.",
							minLength: 1,
							maxLength: 65536,
							format: "uri",
							type: "string",
						},
						connect_args: {
							title: "Connect Args",
							description:
								"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
							type: "object",
						},
					},
					block_type_slug: "database-credentials",
					secret_fields: ["password"],
					block_schema_references: {},
				},
				SnowflakeTargetConfigs: {
					title: "SnowflakeTargetConfigs",
					description:
						"Target configs contain credentials and\nsettings, specific to Snowflake.\nTo find valid keys, head to the [Snowflake Profile](\nhttps://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)\npage.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The type of the target configs.",
							default: "snowflake",
							enum: ["snowflake"],
							type: "string",
						},
						schema: {
							title: "Schema",
							description: "The schema to use for the target configs.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
						connector: {
							title: "Connector",
							description: "The connector to use.",
							allOf: [
								{
									$ref: "#/definitions/SnowflakeConnector",
								},
							],
						},
					},
					required: ["connector"],
					block_type_slug: "dbt-cli-snowflake-target-configs",
					secret_fields: [
						"connector.credentials.password",
						"connector.credentials.private_key",
						"connector.credentials.private_key_passphrase",
						"connector.credentials.token",
					],
					block_schema_references: {
						connector: {
							block_schema_checksum:
								"sha256:a8cba7cafe80dd13d0dc167f351c2dda8d17698b02c7a2f9e7e0fceb1da00994",
							block_type_slug: "snowflake-connector",
						},
					},
				},
				SnowflakeConnector: {
					title: "SnowflakeConnector",
					description: "Perform data operations against a Snowflake database.",
					type: "object",
					properties: {
						credentials: {
							title: "Credentials",
							description: "The credentials to authenticate with Snowflake.",
							allOf: [
								{
									$ref: "#/definitions/SnowflakeCredentials",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the default database to use.",
							type: "string",
						},
						warehouse: {
							title: "Warehouse",
							description: "The name of the default warehouse to use.",
							type: "string",
						},
						schema: {
							title: "Schema",
							description: "The name of the default schema to use.",
							type: "string",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The default number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
						poll_frequency_s: {
							title: "Poll Frequency [seconds]",
							description:
								"The number of seconds between checking query status for long running queries.",
							default: 1,
							type: "integer",
						},
					},
					required: ["credentials", "database", "warehouse", "schema"],
					block_type_slug: "snowflake-connector",
					secret_fields: [
						"credentials.password",
						"credentials.private_key",
						"credentials.private_key_passphrase",
						"credentials.token",
					],
					block_schema_references: {
						credentials: {
							block_schema_checksum:
								"sha256:35bea1e0ca2277b003ca6d1c220e59ce9a58330934c051fe26a549c2fa380b1f",
							block_type_slug: "snowflake-credentials",
						},
					},
				},
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
				TargetConfigs: {
					title: "TargetConfigs",
					description:
						"Target configs contain credentials and\nsettings, specific to the warehouse you're connecting to.\nTo find valid keys, head to the [Available adapters](\nhttps://docs.getdbt.com/docs/available-adapters) page and\nclick the desired adapter's \"Profile Setup\" hyperlink.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The name of the database warehouse.",
							type: "string",
						},
						schema: {
							title: "Schema",
							description:
								"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
					},
					required: ["type", "schema"],
					block_type_slug: "dbt-cli-target-configs",
					secret_fields: [],
					block_schema_references: {},
				},
				GlobalConfigs: {
					title: "GlobalConfigs",
					description:
						"Global configs control things like the visual output\nof logs, the manner in which dbt parses your project,\nand what to do when dbt finds a version mismatch\nor a failing model. Docs can be found [here](\nhttps://docs.getdbt.com/reference/global-configs).",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						send_anonymous_usage_stats: {
							title: "Send Anonymous Usage Stats",
							description: "Whether usage stats are sent to dbt.",
							type: "boolean",
						},
						use_colors: {
							title: "Use Colors",
							description: "Colorize the output it prints in your terminal.",
							type: "boolean",
						},
						partial_parse: {
							title: "Partial Parse",
							description:
								"When partial parsing is enabled, dbt will use an stored internal manifest to determine which files have been changed (if any) since it last parsed the project.",
							type: "boolean",
						},
						printer_width: {
							title: "Printer Width",
							description: "Length of characters before starting a new line.",
							type: "integer",
						},
						write_json: {
							title: "Write Json",
							description:
								"Determines whether dbt writes JSON artifacts to the target/ directory.",
							type: "boolean",
						},
						warn_error: {
							title: "Warn Error",
							description: "Whether to convert dbt warnings into errors.",
							type: "boolean",
						},
						log_format: {
							title: "Log Format",
							description:
								"The LOG_FORMAT config specifies how dbt's logs should be formatted. If the value of this config is json, dbt will output fully structured logs in JSON format.",
							type: "string",
						},
						debug: {
							title: "Debug",
							description:
								"Whether to redirect dbt's debug logs to standard out.",
							type: "boolean",
						},
						version_check: {
							title: "Version Check",
							description:
								"Whether to raise an error if a project's version is used with an incompatible dbt version.",
							type: "boolean",
						},
						fail_fast: {
							title: "Fail Fast",
							description:
								"Make dbt exit immediately if a single resource fails to build.",
							type: "boolean",
						},
						use_experimental_parser: {
							title: "Use Experimental Parser",
							description:
								"Opt into the latest experimental version of the static parser.",
							type: "boolean",
						},
						static_parser: {
							title: "Static Parser",
							description:
								"Whether to use the [static parser](https://docs.getdbt.com/reference/parsing#static-parser).",
							type: "boolean",
						},
					},
					block_type_slug: "dbt-cli-global-configs",
					secret_fields: [],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				dbt_cli_profile: {
					block_schema_checksum:
						"sha256:f55b0f96cb9e1cf2f508bb882b25d9246b351be8b0ad18140a73281674a40d6d",
					block_type_slug: "dbt-cli-profile",
				},
			},
		},
		block_type_id: "3f8dc3f0-e7cd-40f9-a197-b0ecfb66c172",
		block_type: {
			id: "3f8dc3f0-e7cd-40f9-a197-b0ecfb66c172",
			created: "2024-12-02T18:19:08.058075Z",
			updated: "2024-12-02T18:19:08.058077Z",
			name: "dbt Core Operation",
			slug: "dbt-core-operation",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/commands/#prefect_dbt.cli.commands.DbtCoreOperation",
			description:
				"A block representing a dbt operation, containing multiple dbt and shell commands.\n\nFor long-lasting operations, use the trigger method and utilize the block as a\ncontext manager for automatic closure of processes when context is exited.\nIf not, manually call the close method to close processes.\n\nFor short-lasting operations, use the run method. Context is automatically managed\nwith this method. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load a configured block.\n```python\nfrom prefect_dbt import DbtCoreOperation\n\ndbt_op = DbtCoreOperation.load("BLOCK_NAME")\n```\n\nExecute short-lasting dbt debug and list with a custom DbtCliProfile.\n```python\nfrom prefect_dbt import DbtCoreOperation, DbtCliProfile\nfrom prefect_dbt.cli.configs import SnowflakeTargetConfigs\nfrom prefect_snowflake import SnowflakeConnector\n\nsnowflake_connector = await SnowflakeConnector.load("snowflake-connector")\ntarget_configs = SnowflakeTargetConfigs(connector=snowflake_connector)\ndbt_cli_profile = DbtCliProfile(\n    name="jaffle_shop",\n    target="dev",\n    target_configs=target_configs,\n)\ndbt_init = DbtCoreOperation(\n    commands=["dbt debug", "dbt list"],\n    dbt_cli_profile=dbt_cli_profile,\n    overwrite_profiles=True\n)\ndbt_init.run()\n```\n\nExecute a longer-lasting dbt run as a context manager.\n```python\nwith DbtCoreOperation(commands=["dbt run"]) as dbt_run:\n    dbt_process = dbt_run.trigger()\n    # do other things\n    dbt_process.wait_for_completion()\n    dbt_output = dbt_process.fetch_result()\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "9c171aa5-cce3-4647-be2e-23d437bb3fef",
		created: "2024-12-02T18:19:08.167086Z",
		updated: "2024-12-02T18:19:08.167087Z",
		checksum:
			"sha256:0e1b2e94e09041e7d732822354503e87b99ddb31422d9d2c83c671be249aa231",
		fields: {
			title: "DbtCloudCredentials",
			description:
				"Credentials block for credential use across dbt Cloud tasks and flows.",
			type: "object",
			properties: {
				api_key: {
					title: "API Key",
					description: "A dbt Cloud API key to use for authentication.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				account_id: {
					title: "Account ID",
					description: "The ID of your dbt Cloud account.",
					type: "integer",
				},
				domain: {
					title: "Domain",
					description: "The base domain of your dbt Cloud instance.",
					default: "cloud.getdbt.com",
					type: "string",
				},
			},
			required: ["api_key", "account_id"],
			block_type_slug: "dbt-cloud-credentials",
			secret_fields: ["api_key"],
			block_schema_references: {},
		},
		block_type_id: "4e22c349-e2be-4e07-aa37-130bcb17c36e",
		block_type: {
			id: "4e22c349-e2be-4e07-aa37-130bcb17c36e",
			created: "2024-12-02T18:19:08.057417Z",
			updated: "2024-12-02T18:19:08.057418Z",
			name: "dbt Cloud Credentials",
			slug: "dbt-cloud-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cloud/credentials/#prefect_dbt.cloud.credentials.DbtCloudCredentials",
			description:
				"Credentials block for credential use across dbt Cloud tasks and flows. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored dbt Cloud credentials:\n```python\nfrom prefect_dbt.cloud import DbtCloudCredentials\n\ndbt_cloud_credentials = DbtCloudCredentials.load("BLOCK_NAME")\n```\n\nUse DbtCloudCredentials instance to trigger a job run:\n```python\nfrom prefect_dbt.cloud import DbtCloudCredentials\n\ncredentials = DbtCloudCredentials(api_key="my_api_key", account_id=123456789)\n\nasync with dbt_cloud_credentials.get_administrative_client() as client:\n    client.trigger_job_run(job_id=1)\n```\n\nLoad saved dbt Cloud credentials within a flow:\n```python\nfrom prefect import flow\n\nfrom prefect_dbt.cloud import DbtCloudCredentials\nfrom prefect_dbt.cloud.jobs import trigger_dbt_cloud_job_run\n\n\n@flow\ndef trigger_dbt_cloud_job_run_flow():\n    credentials = DbtCloudCredentials.load("my-dbt-credentials")\n    trigger_dbt_cloud_job_run(dbt_cloud_credentials=credentials, job_id=1)\n\ntrigger_dbt_cloud_job_run_flow()\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "0f9b0cb7-7565-4af3-b1cd-5fa24d257a78",
		created: "2024-12-02T18:19:08.164969Z",
		updated: "2024-12-02T18:19:08.164971Z",
		checksum:
			"sha256:85f7476977e725617af89930889b843147320b2df37df911e24806dd6dacc870",
		fields: {
			title: "TargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to the warehouse you're connecting to.\nTo find valid keys, head to the [Available adapters](\nhttps://docs.getdbt.com/docs/available-adapters) page and\nclick the desired adapter's \"Profile Setup\" hyperlink.",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				type: {
					title: "Type",
					description: "The name of the database warehouse.",
					type: "string",
				},
				schema: {
					title: "Schema",
					description:
						"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
					type: "string",
				},
				threads: {
					title: "Threads",
					description:
						"The number of threads representing the max number of paths through the graph dbt may work on at once.",
					default: 4,
					type: "integer",
				},
			},
			required: ["type", "schema"],
			block_type_slug: "dbt-cli-target-configs",
			secret_fields: [],
			block_schema_references: {},
		},
		block_type_id: "5e7375a6-295f-4223-ac70-8c5a5ee669fe",
		block_type: {
			id: "5e7375a6-295f-4223-ac70-8c5a5ee669fe",
			created: "2024-12-02T18:19:08.056737Z",
			updated: "2024-12-02T18:19:08.056738Z",
			name: "dbt CLI Target Configs",
			slug: "dbt-cli-target-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/base/#prefect_dbt.cli.configs.base.TargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to the warehouse you're connecting to.\nTo find valid keys, head to the [Available adapters](\nhttps://docs.getdbt.com/docs/available-adapters) page and\nclick the desired adapter's \"Profile Setup\" hyperlink. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored TargetConfigs:\n```python\nfrom prefect_dbt.cli.configs import TargetConfigs\n\ndbt_cli_target_configs = TargetConfigs.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "ffd690b6-e111-4c16-8aca-7e31832a271e",
		created: "2024-12-02T18:19:08.161504Z",
		updated: "2024-12-02T18:19:08.161505Z",
		checksum:
			"sha256:b24edfb413527c951cb2a8b4b4c16aec096523f871d941889e29ac2e6e92e036",
		fields: {
			title: "SnowflakeCredentials",
			description: "Block used to manage authentication with Snowflake.",
			type: "object",
			properties: {
				account: {
					title: "Account",
					description: "The snowflake account name.",
					example: "nh12345.us-east-2.aws",
					type: "string",
				},
				user: {
					title: "User",
					description: "The user name used to authenticate.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				private_key: {
					title: "Private Key",
					description: "The PEM used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				private_key_path: {
					title: "Private Key Path",
					description: "The path to the private key.",
					type: "string",
					format: "path",
				},
				private_key_passphrase: {
					title: "Private Key Passphrase",
					description: "The password to use for the private key.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				authenticator: {
					title: "Authenticator",
					description:
						"The type of authenticator to use for initializing connection.",
					default: "snowflake",
					enum: [
						"snowflake",
						"snowflake_jwt",
						"externalbrowser",
						"okta_endpoint",
						"oauth",
						"username_password_mfa",
					],
					type: "string",
				},
				token: {
					title: "Token",
					description:
						"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				endpoint: {
					title: "Endpoint",
					description:
						"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
					type: "string",
				},
				role: {
					title: "Role",
					description: "The name of the default role to use.",
					type: "string",
				},
				autocommit: {
					title: "Autocommit",
					description: "Whether to automatically commit.",
					type: "boolean",
				},
			},
			required: ["account", "user"],
			block_type_slug: "snowflake-credentials",
			secret_fields: [
				"password",
				"private_key",
				"private_key_passphrase",
				"token",
			],
			block_schema_references: {},
		},
		block_type_id: "6751e26c-5068-40ef-8473-347d71a08e57",
		block_type: {
			id: "6751e26c-5068-40ef-8473-347d71a08e57",
			created: "2024-12-02T18:19:08.069749Z",
			updated: "2024-12-02T18:19:08.069750Z",
			name: "Snowflake Credentials",
			slug: "snowflake-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-snowflake/credentials/#prefect_snowflake.credentials.SnowflakeCredentials",
			description:
				"Block used to manage authentication with Snowflake. This block is part of the prefect-snowflake collection. Install prefect-snowflake with `pip install prefect-snowflake` to use this block.",
			code_example:
				'Load stored Snowflake credentials:\n```python\nfrom prefect_snowflake import SnowflakeCredentials\n\nsnowflake_credentials_block = SnowflakeCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "28b8aff7-eaf5-42bd-8ae8-48f8b86c42d7",
		created: "2024-12-02T18:19:08.159166Z",
		updated: "2024-12-02T18:19:08.159168Z",
		checksum:
			"sha256:dd0d36d69bbe0d44870fd754f3c00754e37e3f52209590083eaee4c585ce0bd0",
		fields: {
			title: "SnowflakeConnector",
			description: "Perform data operations against a Snowflake database.",
			type: "object",
			properties: {
				credentials: {
					title: "Credentials",
					description: "The credentials to authenticate with Snowflake.",
					allOf: [
						{
							$ref: "#/definitions/SnowflakeCredentials",
						},
					],
				},
				database: {
					title: "Database",
					description: "The name of the default database to use.",
					type: "string",
				},
				warehouse: {
					title: "Warehouse",
					description: "The name of the default warehouse to use.",
					type: "string",
				},
				schema: {
					title: "Schema",
					description: "The name of the default schema to use.",
					type: "string",
				},
				fetch_size: {
					title: "Fetch Size",
					description: "The default number of rows to fetch at a time.",
					default: 1,
					type: "integer",
				},
				poll_frequency_s: {
					title: "Poll Frequency [seconds]",
					description:
						"The number of seconds between checking query status for long running queries.",
					default: 1,
					type: "integer",
				},
			},
			required: ["credentials", "database", "warehouse", "schema"],
			block_type_slug: "snowflake-connector",
			secret_fields: [
				"credentials.password",
				"credentials.private_key",
				"credentials.private_key_passphrase",
				"credentials.token",
			],
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:b24edfb413527c951cb2a8b4b4c16aec096523f871d941889e29ac2e6e92e036",
					block_type_slug: "snowflake-credentials",
				},
			},
			definitions: {
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "854376a0-5920-4f44-9cdb-644e342e4618",
		block_type: {
			id: "854376a0-5920-4f44-9cdb-644e342e4618",
			created: "2024-12-02T18:19:08.069093Z",
			updated: "2024-12-02T18:19:08.069094Z",
			name: "Snowflake Connector",
			slug: "snowflake-connector",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-snowflake/database/#prefect_snowflake.database.SnowflakeConnector",
			description:
				"Perform data operations against a Snowflake database. This block is part of the prefect-snowflake collection. Install prefect-snowflake with `pip install prefect-snowflake` to use this block.",
			code_example:
				'Load stored Snowflake connector as a context manager:\n```python\nfrom prefect_snowflake.database import SnowflakeConnector\n\nsnowflake_connector = SnowflakeConnector.load("BLOCK_NAME"):\n```\n\nInsert data into database and fetch results.\n```python\nfrom prefect_snowflake.database import SnowflakeConnector\n\nwith SnowflakeConnector.load("BLOCK_NAME") as conn:\n    conn.execute(\n        "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"\n    )\n    conn.execute_many(\n        "INSERT INTO customers (name, address) VALUES (%(name)s, %(address)s);",\n        seq_of_parameters=[\n            {"name": "Ford", "address": "Highway 42"},\n            {"name": "Unknown", "address": "Space"},\n            {"name": "Me", "address": "Myway 88"},\n        ],\n    )\n    results = conn.fetch_all(\n        "SELECT * FROM customers WHERE address = %(address)s",\n        parameters={"address": "Space"}\n    )\n    print(results)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "5f02968f-dd0b-4211-b016-57580338514d",
		created: "2024-12-02T18:19:08.156855Z",
		updated: "2024-12-02T18:19:08.156856Z",
		checksum:
			"sha256:1e5be296bb63d7e2b04f0e9b99543db12521af269399d10e2bc290da4244a575",
		fields: {
			title: "SnowflakeTargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to Snowflake.\nTo find valid keys, head to the [Snowflake Profile](\nhttps://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)\npage.",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				type: {
					title: "Type",
					description: "The type of the target configs.",
					default: "snowflake",
					enum: ["snowflake"],
					type: "string",
				},
				schema: {
					title: "Schema",
					description: "The schema to use for the target configs.",
					type: "string",
				},
				threads: {
					title: "Threads",
					description:
						"The number of threads representing the max number of paths through the graph dbt may work on at once.",
					default: 4,
					type: "integer",
				},
				connector: {
					title: "Connector",
					description: "The connector to use.",
					allOf: [
						{
							$ref: "#/definitions/SnowflakeConnector",
						},
					],
				},
			},
			required: ["connector"],
			block_type_slug: "dbt-cli-snowflake-target-configs",
			secret_fields: [
				"connector.credentials.password",
				"connector.credentials.private_key",
				"connector.credentials.private_key_passphrase",
				"connector.credentials.token",
			],
			block_schema_references: {
				connector: {
					block_schema_checksum:
						"sha256:dd0d36d69bbe0d44870fd754f3c00754e37e3f52209590083eaee4c585ce0bd0",
					block_type_slug: "snowflake-connector",
				},
			},
			definitions: {
				SnowflakeConnector: {
					title: "SnowflakeConnector",
					description: "Perform data operations against a Snowflake database.",
					type: "object",
					properties: {
						credentials: {
							title: "Credentials",
							description: "The credentials to authenticate with Snowflake.",
							allOf: [
								{
									$ref: "#/definitions/SnowflakeCredentials",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the default database to use.",
							type: "string",
						},
						warehouse: {
							title: "Warehouse",
							description: "The name of the default warehouse to use.",
							type: "string",
						},
						schema: {
							title: "Schema",
							description: "The name of the default schema to use.",
							type: "string",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The default number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
						poll_frequency_s: {
							title: "Poll Frequency [seconds]",
							description:
								"The number of seconds between checking query status for long running queries.",
							default: 1,
							type: "integer",
						},
					},
					required: ["credentials", "database", "warehouse", "schema"],
					block_type_slug: "snowflake-connector",
					secret_fields: [
						"credentials.password",
						"credentials.private_key",
						"credentials.private_key_passphrase",
						"credentials.token",
					],
					block_schema_references: {
						credentials: {
							block_schema_checksum:
								"sha256:b24edfb413527c951cb2a8b4b4c16aec096523f871d941889e29ac2e6e92e036",
							block_type_slug: "snowflake-credentials",
						},
					},
				},
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "48ec41bc-22b0-4232-b230-583a0c23db17",
		block_type: {
			id: "48ec41bc-22b0-4232-b230-583a0c23db17",
			created: "2024-12-02T18:19:08.056100Z",
			updated: "2024-12-02T18:19:08.056102Z",
			name: "dbt CLI Snowflake Target Configs",
			slug: "dbt-cli-snowflake-target-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/snowflake/#prefect_dbt.cli.configs.snowflake.SnowflakeTargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to Snowflake.\nTo find valid keys, head to the [Snowflake Profile](\nhttps://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)\npage. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored SnowflakeTargetConfigs:\n```python\nfrom prefect_dbt.cli.configs import SnowflakeTargetConfigs\n\nsnowflake_target_configs = SnowflakeTargetConfigs.load("BLOCK_NAME")\n```\n\nInstantiate SnowflakeTargetConfigs.\n```python\nfrom prefect_dbt.cli.configs import SnowflakeTargetConfigs\nfrom prefect_snowflake.credentials import SnowflakeCredentials\nfrom prefect_snowflake.database import SnowflakeConnector\n\ncredentials = SnowflakeCredentials(\n    user="user",\n    password="password",\n    account="account.region.aws",\n    role="role",\n)\nconnector = SnowflakeConnector(\n    schema="public",\n    database="database",\n    warehouse="warehouse",\n    credentials=credentials,\n)\ntarget_configs = SnowflakeTargetConfigs(\n    connector=connector,\n    extras={"retry_on_database_errors": True},\n)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "7c781602-624f-4f52-8e05-16f1170a2f0d",
		created: "2024-12-02T18:19:08.152034Z",
		updated: "2024-12-02T18:19:08.152035Z",
		checksum:
			"sha256:d0c8411280a2529a973b70fb86142959008aad2fe3844c63ab03190e232f776a",
		fields: {
			title: "TargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to the warehouse you're connecting to.\nTo find valid keys, head to the [Available adapters](\nhttps://docs.getdbt.com/docs/available-adapters) page and\nclick the desired adapter's \"Profile Setup\" hyperlink.",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				type: {
					title: "Type",
					description: "The name of the database warehouse.",
					type: "string",
				},
				schema: {
					title: "Schema",
					description:
						"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
					type: "string",
				},
				threads: {
					title: "Threads",
					description:
						"The number of threads representing the max number of paths through the graph dbt may work on at once.",
					default: 4,
					type: "integer",
				},
			},
			required: ["type", "schema"],
			block_type_slug: "dbt-cli-target-configs",
			secret_fields: [],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "5e7375a6-295f-4223-ac70-8c5a5ee669fe",
		block_type: {
			id: "5e7375a6-295f-4223-ac70-8c5a5ee669fe",
			created: "2024-12-02T18:19:08.056737Z",
			updated: "2024-12-02T18:19:08.056738Z",
			name: "dbt CLI Target Configs",
			slug: "dbt-cli-target-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/base/#prefect_dbt.cli.configs.base.TargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to the warehouse you're connecting to.\nTo find valid keys, head to the [Available adapters](\nhttps://docs.getdbt.com/docs/available-adapters) page and\nclick the desired adapter's \"Profile Setup\" hyperlink. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored TargetConfigs:\n```python\nfrom prefect_dbt.cli.configs import TargetConfigs\n\ndbt_cli_target_configs = TargetConfigs.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "627bd7f1-024e-4ec9-beed-749d2b98c970",
		created: "2024-12-02T18:19:08.142975Z",
		updated: "2024-12-02T18:19:08.142976Z",
		checksum:
			"sha256:35bea1e0ca2277b003ca6d1c220e59ce9a58330934c051fe26a549c2fa380b1f",
		fields: {
			title: "SnowflakeCredentials",
			description: "Block used to manage authentication with Snowflake.",
			type: "object",
			properties: {
				account: {
					title: "Account",
					description: "The snowflake account name.",
					example: "nh12345.us-east-2.aws",
					type: "string",
				},
				user: {
					title: "User",
					description: "The user name used to authenticate.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				private_key: {
					title: "Private Key",
					description: "The PEM used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				private_key_path: {
					title: "Private Key Path",
					description: "The path to the private key.",
					type: "string",
					format: "path",
				},
				private_key_passphrase: {
					title: "Private Key Passphrase",
					description: "The password to use for the private key.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				authenticator: {
					title: "Authenticator",
					description:
						"The type of authenticator to use for initializing connection.",
					default: "snowflake",
					enum: [
						"snowflake",
						"snowflake_jwt",
						"externalbrowser",
						"okta_endpoint",
						"oauth",
						"username_password_mfa",
					],
					type: "string",
				},
				token: {
					title: "Token",
					description:
						"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				endpoint: {
					title: "Endpoint",
					description:
						"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
					type: "string",
				},
				role: {
					title: "Role",
					description: "The name of the default role to use.",
					type: "string",
				},
				autocommit: {
					title: "Autocommit",
					description: "Whether to automatically commit.",
					type: "boolean",
				},
			},
			required: ["account", "user"],
			block_type_slug: "snowflake-credentials",
			secret_fields: [
				"password",
				"private_key",
				"private_key_passphrase",
				"token",
			],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "6751e26c-5068-40ef-8473-347d71a08e57",
		block_type: {
			id: "6751e26c-5068-40ef-8473-347d71a08e57",
			created: "2024-12-02T18:19:08.069749Z",
			updated: "2024-12-02T18:19:08.069750Z",
			name: "Snowflake Credentials",
			slug: "snowflake-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-snowflake/credentials/#prefect_snowflake.credentials.SnowflakeCredentials",
			description:
				"Block used to manage authentication with Snowflake. This block is part of the prefect-snowflake collection. Install prefect-snowflake with `pip install prefect-snowflake` to use this block.",
			code_example:
				'Load stored Snowflake credentials:\n```python\nfrom prefect_snowflake import SnowflakeCredentials\n\nsnowflake_credentials_block = SnowflakeCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "bd4b6ac2-0cb3-431c-a430-9a4991439520",
		created: "2024-12-02T18:19:08.140383Z",
		updated: "2024-12-02T18:19:08.140385Z",
		checksum:
			"sha256:a8cba7cafe80dd13d0dc167f351c2dda8d17698b02c7a2f9e7e0fceb1da00994",
		fields: {
			title: "SnowflakeConnector",
			description: "Perform data operations against a Snowflake database.",
			type: "object",
			properties: {
				credentials: {
					title: "Credentials",
					description: "The credentials to authenticate with Snowflake.",
					allOf: [
						{
							$ref: "#/definitions/SnowflakeCredentials",
						},
					],
				},
				database: {
					title: "Database",
					description: "The name of the default database to use.",
					type: "string",
				},
				warehouse: {
					title: "Warehouse",
					description: "The name of the default warehouse to use.",
					type: "string",
				},
				schema: {
					title: "Schema",
					description: "The name of the default schema to use.",
					type: "string",
				},
				fetch_size: {
					title: "Fetch Size",
					description: "The default number of rows to fetch at a time.",
					default: 1,
					type: "integer",
				},
				poll_frequency_s: {
					title: "Poll Frequency [seconds]",
					description:
						"The number of seconds between checking query status for long running queries.",
					default: 1,
					type: "integer",
				},
			},
			required: ["credentials", "database", "warehouse", "schema"],
			block_type_slug: "snowflake-connector",
			secret_fields: [
				"credentials.password",
				"credentials.private_key",
				"credentials.private_key_passphrase",
				"credentials.token",
			],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:35bea1e0ca2277b003ca6d1c220e59ce9a58330934c051fe26a549c2fa380b1f",
					block_type_slug: "snowflake-credentials",
				},
			},
		},
		block_type_id: "854376a0-5920-4f44-9cdb-644e342e4618",
		block_type: {
			id: "854376a0-5920-4f44-9cdb-644e342e4618",
			created: "2024-12-02T18:19:08.069093Z",
			updated: "2024-12-02T18:19:08.069094Z",
			name: "Snowflake Connector",
			slug: "snowflake-connector",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-snowflake/database/#prefect_snowflake.database.SnowflakeConnector",
			description:
				"Perform data operations against a Snowflake database. This block is part of the prefect-snowflake collection. Install prefect-snowflake with `pip install prefect-snowflake` to use this block.",
			code_example:
				'Load stored Snowflake connector as a context manager:\n```python\nfrom prefect_snowflake.database import SnowflakeConnector\n\nsnowflake_connector = SnowflakeConnector.load("BLOCK_NAME"):\n```\n\nInsert data into database and fetch results.\n```python\nfrom prefect_snowflake.database import SnowflakeConnector\n\nwith SnowflakeConnector.load("BLOCK_NAME") as conn:\n    conn.execute(\n        "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"\n    )\n    conn.execute_many(\n        "INSERT INTO customers (name, address) VALUES (%(name)s, %(address)s);",\n        seq_of_parameters=[\n            {"name": "Ford", "address": "Highway 42"},\n            {"name": "Unknown", "address": "Space"},\n            {"name": "Me", "address": "Myway 88"},\n        ],\n    )\n    results = conn.fetch_all(\n        "SELECT * FROM customers WHERE address = %(address)s",\n        parameters={"address": "Space"}\n    )\n    print(results)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "7a8ab18f-cab8-4437-93f2-a52550246f0d",
		created: "2024-12-02T18:19:08.137806Z",
		updated: "2024-12-02T18:19:08.137807Z",
		checksum:
			"sha256:a70fca75226dc280c38ab0dda3679d3b0ffdee21af4463f3fb1ad6278405e370",
		fields: {
			title: "SnowflakeTargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to Snowflake.\nTo find valid keys, head to the [Snowflake Profile](\nhttps://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)\npage.",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				type: {
					title: "Type",
					description: "The type of the target configs.",
					default: "snowflake",
					enum: ["snowflake"],
					type: "string",
				},
				schema: {
					title: "Schema",
					description: "The schema to use for the target configs.",
					type: "string",
				},
				threads: {
					title: "Threads",
					description:
						"The number of threads representing the max number of paths through the graph dbt may work on at once.",
					default: 4,
					type: "integer",
				},
				connector: {
					title: "Connector",
					description: "The connector to use.",
					allOf: [
						{
							$ref: "#/definitions/SnowflakeConnector",
						},
					],
				},
			},
			required: ["connector"],
			block_type_slug: "dbt-cli-snowflake-target-configs",
			secret_fields: [
				"connector.credentials.password",
				"connector.credentials.private_key",
				"connector.credentials.private_key_passphrase",
				"connector.credentials.token",
			],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				SnowflakeConnector: {
					title: "SnowflakeConnector",
					description: "Perform data operations against a Snowflake database.",
					type: "object",
					properties: {
						credentials: {
							title: "Credentials",
							description: "The credentials to authenticate with Snowflake.",
							allOf: [
								{
									$ref: "#/definitions/SnowflakeCredentials",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the default database to use.",
							type: "string",
						},
						warehouse: {
							title: "Warehouse",
							description: "The name of the default warehouse to use.",
							type: "string",
						},
						schema: {
							title: "Schema",
							description: "The name of the default schema to use.",
							type: "string",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The default number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
						poll_frequency_s: {
							title: "Poll Frequency [seconds]",
							description:
								"The number of seconds between checking query status for long running queries.",
							default: 1,
							type: "integer",
						},
					},
					required: ["credentials", "database", "warehouse", "schema"],
					block_type_slug: "snowflake-connector",
					secret_fields: [
						"credentials.password",
						"credentials.private_key",
						"credentials.private_key_passphrase",
						"credentials.token",
					],
					block_schema_references: {
						credentials: {
							block_schema_checksum:
								"sha256:35bea1e0ca2277b003ca6d1c220e59ce9a58330934c051fe26a549c2fa380b1f",
							block_type_slug: "snowflake-credentials",
						},
					},
				},
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				connector: {
					block_schema_checksum:
						"sha256:a8cba7cafe80dd13d0dc167f351c2dda8d17698b02c7a2f9e7e0fceb1da00994",
					block_type_slug: "snowflake-connector",
				},
			},
		},
		block_type_id: "48ec41bc-22b0-4232-b230-583a0c23db17",
		block_type: {
			id: "48ec41bc-22b0-4232-b230-583a0c23db17",
			created: "2024-12-02T18:19:08.056100Z",
			updated: "2024-12-02T18:19:08.056102Z",
			name: "dbt CLI Snowflake Target Configs",
			slug: "dbt-cli-snowflake-target-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/snowflake/#prefect_dbt.cli.configs.snowflake.SnowflakeTargetConfigs",
			description:
				"Target configs contain credentials and\nsettings, specific to Snowflake.\nTo find valid keys, head to the [Snowflake Profile](\nhttps://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)\npage. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored SnowflakeTargetConfigs:\n```python\nfrom prefect_dbt.cli.configs import SnowflakeTargetConfigs\n\nsnowflake_target_configs = SnowflakeTargetConfigs.load("BLOCK_NAME")\n```\n\nInstantiate SnowflakeTargetConfigs.\n```python\nfrom prefect_dbt.cli.configs import SnowflakeTargetConfigs\nfrom prefect_snowflake.credentials import SnowflakeCredentials\nfrom prefect_snowflake.database import SnowflakeConnector\n\ncredentials = SnowflakeCredentials(\n    user="user",\n    password="password",\n    account="account.region.aws",\n    role="role",\n)\nconnector = SnowflakeConnector(\n    schema="public",\n    database="database",\n    warehouse="warehouse",\n    credentials=credentials,\n)\ntarget_configs = SnowflakeTargetConfigs(\n    connector=connector,\n    extras={"retry_on_database_errors": True},\n)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "90c8bbaa-ff00-48b2-8cae-ff94ce82278e",
		created: "2024-12-02T18:19:08.135243Z",
		updated: "2024-12-02T18:19:08.135245Z",
		checksum:
			"sha256:f55b0f96cb9e1cf2f508bb882b25d9246b351be8b0ad18140a73281674a40d6d",
		fields: {
			title: "DbtCliProfile",
			description: "Profile for use across dbt CLI tasks and flows.",
			type: "object",
			properties: {
				name: {
					title: "Name",
					description: "Profile name used for populating profiles.yml.",
					type: "string",
				},
				target: {
					title: "Target",
					description: "The default target your dbt project will use.",
					type: "string",
				},
				target_configs: {
					title: "Target Configs",
					description:
						"Target configs contain credentials and settings, specific to the warehouse you're connecting to.",
					anyOf: [
						{
							$ref: "#/definitions/SnowflakeTargetConfigs",
						},
						{
							$ref: "#/definitions/BigQueryTargetConfigs",
						},
						{
							$ref: "#/definitions/PostgresTargetConfigs",
						},
						{
							$ref: "#/definitions/TargetConfigs",
						},
					],
				},
				global_configs: {
					title: "Global Configs",
					description:
						"Global configs control things like the visual output of logs, the manner in which dbt parses your project, and what to do when dbt finds a version mismatch or a failing model.",
					allOf: [
						{
							$ref: "#/definitions/GlobalConfigs",
						},
					],
				},
			},
			required: ["name", "target", "target_configs"],
			block_type_slug: "dbt-cli-profile",
			secret_fields: [
				"target_configs.connector.credentials.password",
				"target_configs.connector.credentials.private_key",
				"target_configs.connector.credentials.private_key_passphrase",
				"target_configs.connector.credentials.token",
				"target_configs.credentials.service_account_info.*",
				"target_configs.credentials.connection_info.password",
				"target_configs.credentials.password",
			],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				BigQueryTargetConfigs: {
					title: "BigQueryTargetConfigs",
					description:
						"dbt CLI target configs containing credentials and settings, specific to BigQuery.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The type of target.",
							default: "bigquery",
							enum: ["bigquery"],
							type: "string",
						},
						schema: {
							title: "Schema",
							description:
								"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
						project: {
							title: "Project",
							description: "The project to use.",
							type: "string",
						},
						credentials: {
							title: "Credentials",
							description: "The credentials to use to authenticate.",
							allOf: [
								{
									$ref: "#/definitions/GcpCredentials",
								},
							],
						},
					},
					required: ["schema"],
					block_type_slug: "dbt-cli-bigquery-target-configs",
					secret_fields: ["credentials.service_account_info.*"],
					block_schema_references: {
						credentials: {
							block_schema_checksum:
								"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
							block_type_slug: "gcp-credentials",
						},
					},
				},
				GcpCredentials: {
					title: "GcpCredentials",
					description:
						"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
					type: "object",
					properties: {
						service_account_file: {
							title: "Service Account File",
							description: "Path to the service account JSON keyfile.",
							type: "string",
							format: "path",
						},
						service_account_info: {
							title: "Service Account Info",
							description: "The contents of the keyfile as a dict.",
							type: "object",
						},
						project: {
							title: "Project",
							description: "The GCP project to use for the client.",
							type: "string",
						},
					},
					block_type_slug: "gcp-credentials",
					secret_fields: ["service_account_info.*"],
					block_schema_references: {},
				},
				PostgresTargetConfigs: {
					title: "PostgresTargetConfigs",
					description:
						"dbt CLI target configs containing credentials and settings specific to Postgres.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The type of the target.",
							default: "postgres",
							enum: ["postgres"],
							type: "string",
						},
						schema: {
							title: "Schema",
							description:
								"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
						credentials: {
							title: "Credentials",
							description:
								"The credentials to use to authenticate; if there are duplicate keys between credentials and TargetConfigs, e.g. schema, an error will be raised.",
							anyOf: [
								{
									$ref: "#/definitions/SqlAlchemyConnector",
								},
								{
									$ref: "#/definitions/DatabaseCredentials",
								},
							],
						},
					},
					required: ["schema", "credentials"],
					block_type_slug: "dbt-cli-postgres-target-configs",
					secret_fields: [
						"credentials.connection_info.password",
						"credentials.password",
					],
					block_schema_references: {
						credentials: [
							{
								block_schema_checksum:
									"sha256:01e6c0bdaac125860811b201f5a5e98ffefd5f8a49f1398b6996aec362643acc",
								block_type_slug: "sqlalchemy-connector",
							},
							{
								block_schema_checksum:
									"sha256:64175f83f2ae15bef7893a4d9a02658f2b5288747d54594ca6d356dc42e9993c",
								block_type_slug: "database-credentials",
							},
						],
					},
				},
				SqlAlchemyConnector: {
					title: "SqlAlchemyConnector",
					description:
						"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost.",
					type: "object",
					properties: {
						connection_info: {
							title: "Connection Info",
							description:
								"SQLAlchemy URL to create the engine; either create from components or create from a string.",
							anyOf: [
								{
									$ref: "#/definitions/ConnectionComponents",
								},
								{
									type: "string",
									minLength: 1,
									maxLength: 65536,
									format: "uri",
								},
							],
						},
						connect_args: {
							title: "Additional Connection Arguments",
							description:
								"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
							type: "object",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
					},
					required: ["connection_info"],
					block_type_slug: "sqlalchemy-connector",
					secret_fields: ["connection_info.password"],
					block_schema_references: {},
				},
				DatabaseCredentials: {
					title: "DatabaseCredentials",
					description: "Block used to manage authentication with a database.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
						url: {
							title: "Url",
							description:
								"Manually create and provide a URL to create the engine, this is useful for external dialects, e.g. Snowflake, because some of the params, such as 'warehouse', is not directly supported in the vanilla `sqlalchemy.engine.URL.create` method; do not provide this alongside with other URL params as it will raise a `ValueError`.",
							minLength: 1,
							maxLength: 65536,
							format: "uri",
							type: "string",
						},
						connect_args: {
							title: "Connect Args",
							description:
								"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
							type: "object",
						},
					},
					block_type_slug: "database-credentials",
					secret_fields: ["password"],
					block_schema_references: {},
				},
				SnowflakeTargetConfigs: {
					title: "SnowflakeTargetConfigs",
					description:
						"Target configs contain credentials and\nsettings, specific to Snowflake.\nTo find valid keys, head to the [Snowflake Profile](\nhttps://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)\npage.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The type of the target configs.",
							default: "snowflake",
							enum: ["snowflake"],
							type: "string",
						},
						schema: {
							title: "Schema",
							description: "The schema to use for the target configs.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
						connector: {
							title: "Connector",
							description: "The connector to use.",
							allOf: [
								{
									$ref: "#/definitions/SnowflakeConnector",
								},
							],
						},
					},
					required: ["connector"],
					block_type_slug: "dbt-cli-snowflake-target-configs",
					secret_fields: [
						"connector.credentials.password",
						"connector.credentials.private_key",
						"connector.credentials.private_key_passphrase",
						"connector.credentials.token",
					],
					block_schema_references: {
						connector: {
							block_schema_checksum:
								"sha256:a8cba7cafe80dd13d0dc167f351c2dda8d17698b02c7a2f9e7e0fceb1da00994",
							block_type_slug: "snowflake-connector",
						},
					},
				},
				SnowflakeConnector: {
					title: "SnowflakeConnector",
					description: "Perform data operations against a Snowflake database.",
					type: "object",
					properties: {
						credentials: {
							title: "Credentials",
							description: "The credentials to authenticate with Snowflake.",
							allOf: [
								{
									$ref: "#/definitions/SnowflakeCredentials",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the default database to use.",
							type: "string",
						},
						warehouse: {
							title: "Warehouse",
							description: "The name of the default warehouse to use.",
							type: "string",
						},
						schema: {
							title: "Schema",
							description: "The name of the default schema to use.",
							type: "string",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The default number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
						poll_frequency_s: {
							title: "Poll Frequency [seconds]",
							description:
								"The number of seconds between checking query status for long running queries.",
							default: 1,
							type: "integer",
						},
					},
					required: ["credentials", "database", "warehouse", "schema"],
					block_type_slug: "snowflake-connector",
					secret_fields: [
						"credentials.password",
						"credentials.private_key",
						"credentials.private_key_passphrase",
						"credentials.token",
					],
					block_schema_references: {
						credentials: {
							block_schema_checksum:
								"sha256:35bea1e0ca2277b003ca6d1c220e59ce9a58330934c051fe26a549c2fa380b1f",
							block_type_slug: "snowflake-credentials",
						},
					},
				},
				SnowflakeCredentials: {
					title: "SnowflakeCredentials",
					description: "Block used to manage authentication with Snowflake.",
					type: "object",
					properties: {
						account: {
							title: "Account",
							description: "The snowflake account name.",
							example: "nh12345.us-east-2.aws",
							type: "string",
						},
						user: {
							title: "User",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key: {
							title: "Private Key",
							description: "The PEM used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						private_key_path: {
							title: "Private Key Path",
							description: "The path to the private key.",
							type: "string",
							format: "path",
						},
						private_key_passphrase: {
							title: "Private Key Passphrase",
							description: "The password to use for the private key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						authenticator: {
							title: "Authenticator",
							description:
								"The type of authenticator to use for initializing connection.",
							default: "snowflake",
							enum: [
								"snowflake",
								"snowflake_jwt",
								"externalbrowser",
								"okta_endpoint",
								"oauth",
								"username_password_mfa",
							],
							type: "string",
						},
						token: {
							title: "Token",
							description:
								"The OAuth or JWT Token to provide when authenticator is set to `oauth`.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						endpoint: {
							title: "Endpoint",
							description:
								"The Okta endpoint to use when authenticator is set to `okta_endpoint`.",
							type: "string",
						},
						role: {
							title: "Role",
							description: "The name of the default role to use.",
							type: "string",
						},
						autocommit: {
							title: "Autocommit",
							description: "Whether to automatically commit.",
							type: "boolean",
						},
					},
					required: ["account", "user"],
					block_type_slug: "snowflake-credentials",
					secret_fields: [
						"password",
						"private_key",
						"private_key_passphrase",
						"token",
					],
					block_schema_references: {},
				},
				TargetConfigs: {
					title: "TargetConfigs",
					description:
						"Target configs contain credentials and\nsettings, specific to the warehouse you're connecting to.\nTo find valid keys, head to the [Available adapters](\nhttps://docs.getdbt.com/docs/available-adapters) page and\nclick the desired adapter's \"Profile Setup\" hyperlink.",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						type: {
							title: "Type",
							description: "The name of the database warehouse.",
							type: "string",
						},
						schema: {
							title: "Schema",
							description:
								"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
							type: "string",
						},
						threads: {
							title: "Threads",
							description:
								"The number of threads representing the max number of paths through the graph dbt may work on at once.",
							default: 4,
							type: "integer",
						},
					},
					required: ["type", "schema"],
					block_type_slug: "dbt-cli-target-configs",
					secret_fields: [],
					block_schema_references: {},
				},
				GlobalConfigs: {
					title: "GlobalConfigs",
					description:
						"Global configs control things like the visual output\nof logs, the manner in which dbt parses your project,\nand what to do when dbt finds a version mismatch\nor a failing model. Docs can be found [here](\nhttps://docs.getdbt.com/reference/global-configs).",
					type: "object",
					properties: {
						extras: {
							title: "Extras",
							description:
								"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
							type: "object",
						},
						allow_field_overrides: {
							title: "Allow Field Overrides",
							description:
								"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
							default: false,
							type: "boolean",
						},
						send_anonymous_usage_stats: {
							title: "Send Anonymous Usage Stats",
							description: "Whether usage stats are sent to dbt.",
							type: "boolean",
						},
						use_colors: {
							title: "Use Colors",
							description: "Colorize the output it prints in your terminal.",
							type: "boolean",
						},
						partial_parse: {
							title: "Partial Parse",
							description:
								"When partial parsing is enabled, dbt will use an stored internal manifest to determine which files have been changed (if any) since it last parsed the project.",
							type: "boolean",
						},
						printer_width: {
							title: "Printer Width",
							description: "Length of characters before starting a new line.",
							type: "integer",
						},
						write_json: {
							title: "Write Json",
							description:
								"Determines whether dbt writes JSON artifacts to the target/ directory.",
							type: "boolean",
						},
						warn_error: {
							title: "Warn Error",
							description: "Whether to convert dbt warnings into errors.",
							type: "boolean",
						},
						log_format: {
							title: "Log Format",
							description:
								"The LOG_FORMAT config specifies how dbt's logs should be formatted. If the value of this config is json, dbt will output fully structured logs in JSON format.",
							type: "string",
						},
						debug: {
							title: "Debug",
							description:
								"Whether to redirect dbt's debug logs to standard out.",
							type: "boolean",
						},
						version_check: {
							title: "Version Check",
							description:
								"Whether to raise an error if a project's version is used with an incompatible dbt version.",
							type: "boolean",
						},
						fail_fast: {
							title: "Fail Fast",
							description:
								"Make dbt exit immediately if a single resource fails to build.",
							type: "boolean",
						},
						use_experimental_parser: {
							title: "Use Experimental Parser",
							description:
								"Opt into the latest experimental version of the static parser.",
							type: "boolean",
						},
						static_parser: {
							title: "Static Parser",
							description:
								"Whether to use the [static parser](https://docs.getdbt.com/reference/parsing#static-parser).",
							type: "boolean",
						},
					},
					block_type_slug: "dbt-cli-global-configs",
					secret_fields: [],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				target_configs: [
					{
						block_schema_checksum:
							"sha256:842c5dc7d4d1557eedff36982eafeda7b0803915942f72224a7f627efdbe5ff5",
						block_type_slug: "dbt-cli-bigquery-target-configs",
					},
					{
						block_schema_checksum:
							"sha256:1552a2d5c102961df4082329f39c10b8a51e26ee687148efd6d71ce8be8850c0",
						block_type_slug: "dbt-cli-postgres-target-configs",
					},
					{
						block_schema_checksum:
							"sha256:a70fca75226dc280c38ab0dda3679d3b0ffdee21af4463f3fb1ad6278405e370",
						block_type_slug: "dbt-cli-snowflake-target-configs",
					},
					{
						block_schema_checksum:
							"sha256:d0c8411280a2529a973b70fb86142959008aad2fe3844c63ab03190e232f776a",
						block_type_slug: "dbt-cli-target-configs",
					},
				],
				global_configs: {
					block_schema_checksum:
						"sha256:63df9d18a1aafde1cc8330cd49f81f6600b4ce6db92955973bbf341cc86e916d",
					block_type_slug: "dbt-cli-global-configs",
				},
			},
		},
		block_type_id: "d6d12540-3bd9-4274-a06b-67410dce8781",
		block_type: {
			id: "d6d12540-3bd9-4274-a06b-67410dce8781",
			created: "2024-12-02T18:19:08.055457Z",
			updated: "2024-12-02T18:19:08.055459Z",
			name: "dbt CLI Profile",
			slug: "dbt-cli-profile",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/credentials/#prefect_dbt.cli.credentials.DbtCliProfile",
			description:
				"Profile for use across dbt CLI tasks and flows. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored dbt CLI profile:\n```python\nfrom prefect_dbt.cli import DbtCliProfile\ndbt_cli_profile = DbtCliProfile.load("BLOCK_NAME").get_profile()\n```\n\nGet a dbt Snowflake profile from DbtCliProfile by using SnowflakeTargetConfigs:\n```python\nfrom prefect_dbt.cli import DbtCliProfile\nfrom prefect_dbt.cli.configs import SnowflakeTargetConfigs\nfrom prefect_snowflake.credentials import SnowflakeCredentials\nfrom prefect_snowflake.database import SnowflakeConnector\n\ncredentials = SnowflakeCredentials(\n    user="user",\n    password="password",\n    account="account.region.aws",\n    role="role",\n)\nconnector = SnowflakeConnector(\n    schema="public",\n    database="database",\n    warehouse="warehouse",\n    credentials=credentials,\n)\ntarget_configs = SnowflakeTargetConfigs(\n    connector=connector\n)\ndbt_cli_profile = DbtCliProfile(\n    name="jaffle_shop",\n    target="dev",\n    target_configs=target_configs,\n)\nprofile = dbt_cli_profile.get_profile()\n```\n\nGet a dbt Redshift profile from DbtCliProfile by using generic TargetConfigs:\n```python\nfrom prefect_dbt.cli import DbtCliProfile\nfrom prefect_dbt.cli.configs import GlobalConfigs, TargetConfigs\n\ntarget_configs_extras = dict(\n    host="hostname.region.redshift.amazonaws.com",\n    user="username",\n    password="password1",\n    port=5439,\n    dbname="analytics",\n)\ntarget_configs = TargetConfigs(\n    type="redshift",\n    schema="schema",\n    threads=4,\n    extras=target_configs_extras\n)\ndbt_cli_profile = DbtCliProfile(\n    name="jaffle_shop",\n    target="dev",\n    target_configs=target_configs,\n)\nprofile = dbt_cli_profile.get_profile()\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "358e0562-f39e-4cd4-a23f-20d837ec7588",
		created: "2024-12-02T18:19:08.132079Z",
		updated: "2024-12-02T18:19:08.132080Z",
		checksum:
			"sha256:64175f83f2ae15bef7893a4d9a02658f2b5288747d54594ca6d356dc42e9993c",
		fields: {
			title: "DatabaseCredentials",
			description: "Block used to manage authentication with a database.",
			type: "object",
			properties: {
				driver: {
					title: "Driver",
					description: "The driver name to use.",
					anyOf: [
						{
							$ref: "#/definitions/AsyncDriver",
						},
						{
							$ref: "#/definitions/SyncDriver",
						},
						{
							type: "string",
						},
					],
				},
				username: {
					title: "Username",
					description: "The user name used to authenticate.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password used to authenticate.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				database: {
					title: "Database",
					description: "The name of the database to use.",
					type: "string",
				},
				host: {
					title: "Host",
					description: "The host address of the database.",
					type: "string",
				},
				port: {
					title: "Port",
					description: "The port to connect to the database.",
					type: "string",
				},
				query: {
					title: "Query",
					description:
						"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
					type: "object",
					additionalProperties: {
						type: "string",
					},
				},
				url: {
					title: "Url",
					description:
						"Manually create and provide a URL to create the engine, this is useful for external dialects, e.g. Snowflake, because some of the params, such as 'warehouse', is not directly supported in the vanilla `sqlalchemy.engine.URL.create` method; do not provide this alongside with other URL params as it will raise a `ValueError`.",
					minLength: 1,
					maxLength: 65536,
					format: "uri",
					type: "string",
				},
				connect_args: {
					title: "Connect Args",
					description:
						"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
					type: "object",
				},
			},
			block_type_slug: "database-credentials",
			secret_fields: ["password"],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "075671b0-2a76-47a6-96b6-a7963711acfe",
		block_type: {
			id: "075671b0-2a76-47a6-96b6-a7963711acfe",
			created: "2024-12-02T18:19:08.070452Z",
			updated: "2024-12-02T18:19:08.070453Z",
			name: "Database Credentials",
			slug: "database-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/fb3f4debabcda1c5a3aeea4f5b3f94c28845e23e-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-sqlalchemy/credentials/#prefect_sqlalchemy.credentials.DatabaseCredentials",
			description:
				"Block used to manage authentication with a database. This block is part of the prefect-sqlalchemy collection. Install prefect-sqlalchemy with `pip install prefect-sqlalchemy` to use this block.",
			code_example:
				'Load stored database credentials:\n```python\nfrom prefect_sqlalchemy import DatabaseCredentials\ndatabase_block = DatabaseCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "b545442b-c0aa-4565-88e8-d27e0fcabf86",
		created: "2024-12-02T18:19:08.128936Z",
		updated: "2024-12-02T18:19:08.128937Z",
		checksum:
			"sha256:01e6c0bdaac125860811b201f5a5e98ffefd5f8a49f1398b6996aec362643acc",
		fields: {
			title: "SqlAlchemyConnector",
			description:
				"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost.",
			type: "object",
			properties: {
				connection_info: {
					title: "Connection Info",
					description:
						"SQLAlchemy URL to create the engine; either create from components or create from a string.",
					anyOf: [
						{
							$ref: "#/definitions/ConnectionComponents",
						},
						{
							type: "string",
							minLength: 1,
							maxLength: 65536,
							format: "uri",
						},
					],
				},
				connect_args: {
					title: "Additional Connection Arguments",
					description:
						"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
					type: "object",
				},
				fetch_size: {
					title: "Fetch Size",
					description: "The number of rows to fetch at a time.",
					default: 1,
					type: "integer",
				},
			},
			required: ["connection_info"],
			block_type_slug: "sqlalchemy-connector",
			secret_fields: ["connection_info.password"],
			definitions: {
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
			},
			block_schema_references: {},
		},
		block_type_id: "c840a999-050f-462a-a9a5-cf09b4a10d3d",
		block_type: {
			id: "c840a999-050f-462a-a9a5-cf09b4a10d3d",
			created: "2024-12-02T18:19:08.071111Z",
			updated: "2024-12-02T18:19:08.071112Z",
			name: "SQLAlchemy Connector",
			slug: "sqlalchemy-connector",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/3c7dff04f70aaf4528e184a3b028f9e40b98d68c-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-sqlalchemy/database/#prefect_sqlalchemy.database.SqlAlchemyConnector",
			description:
				"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost. This block is part of the prefect-sqlalchemy collection. Install prefect-sqlalchemy with `pip install prefect-sqlalchemy` to use this block.",
			code_example:
				'Load stored database credentials and use in context manager:\n```python\nfrom prefect_sqlalchemy import SqlAlchemyConnector\n\ndatabase_block = SqlAlchemyConnector.load("BLOCK_NAME")\nwith database_block:\n    ...\n```\n\nCreate table named customers and insert values; then fetch the first 10 rows.\n```python\nfrom prefect_sqlalchemy import (\n    SqlAlchemyConnector, SyncDriver, ConnectionComponents\n)\n\nwith SqlAlchemyConnector(\n    connection_info=ConnectionComponents(\n        driver=SyncDriver.SQLITE_PYSQLITE,\n        database="prefect.db"\n    )\n) as database:\n    database.execute(\n        "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);",\n    )\n    for i in range(1, 42):\n        database.execute(\n            "INSERT INTO customers (name, address) VALUES (:name, :address);",\n            parameters={"name": "Marvin", "address": f"Highway {i}"},\n        )\n    results = database.fetch_many(\n        "SELECT * FROM customers WHERE name = :name;",\n        parameters={"name": "Marvin"},\n        size=10\n    )\nprint(results)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "8301c99d-0199-4add-b955-707c424c11a8",
		created: "2024-12-02T18:19:08.126446Z",
		updated: "2024-12-02T18:19:08.126447Z",
		checksum:
			"sha256:1552a2d5c102961df4082329f39c10b8a51e26ee687148efd6d71ce8be8850c0",
		fields: {
			title: "PostgresTargetConfigs",
			description:
				"dbt CLI target configs containing credentials and settings specific to Postgres.",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				type: {
					title: "Type",
					description: "The type of the target.",
					default: "postgres",
					enum: ["postgres"],
					type: "string",
				},
				schema: {
					title: "Schema",
					description:
						"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
					type: "string",
				},
				threads: {
					title: "Threads",
					description:
						"The number of threads representing the max number of paths through the graph dbt may work on at once.",
					default: 4,
					type: "integer",
				},
				credentials: {
					title: "Credentials",
					description:
						"The credentials to use to authenticate; if there are duplicate keys between credentials and TargetConfigs, e.g. schema, an error will be raised.",
					anyOf: [
						{
							$ref: "#/definitions/SqlAlchemyConnector",
						},
						{
							$ref: "#/definitions/DatabaseCredentials",
						},
					],
				},
			},
			required: ["schema", "credentials"],
			block_type_slug: "dbt-cli-postgres-target-configs",
			secret_fields: [
				"credentials.connection_info.password",
				"credentials.password",
			],
			definitions: {
				AsyncDriver: {
					title: "AsyncDriver",
					description:
						"Known dialects with their corresponding async drivers.\n\nAttributes:\n    POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)\n\n    SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)\n\n    MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)\n    MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)",
					enum: [
						"postgresql+asyncpg",
						"sqlite+aiosqlite",
						"mysql+asyncmy",
						"mysql+aiomysql",
					],
				},
				SyncDriver: {
					title: "SyncDriver",
					description:
						"Known dialects with their corresponding sync drivers.\n\nAttributes:\n    POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)\n    POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)\n    POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)\n    POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)\n    POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)\n\n    MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)\n    MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)\n    MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)\n    MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)\n    MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)\n    MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)\n\n    SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)\n    SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)\n\n    ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)\n\n    MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)\n    MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)\n    MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)",
					enum: [
						"postgresql+psycopg2",
						"postgresql+pg8000",
						"postgresql+psycopg2cffi",
						"postgresql+pypostgresql",
						"postgresql+pygresql",
						"mysql+mysqldb",
						"mysql+pymysql",
						"mysql+mysqlconnector",
						"mysql+cymysql",
						"mysql+oursql",
						"mysql+pyodbc",
						"sqlite+pysqlite",
						"sqlite+pysqlcipher",
						"oracle+cx_oracle",
						"mssql+pyodbc",
						"mssql+mxodbc",
						"mssql+pymssql",
					],
				},
				ConnectionComponents: {
					title: "ConnectionComponents",
					description:
						"Parameters to use to create a SQLAlchemy engine URL.\n\nAttributes:\n    driver: The driver name to use.\n    database: The name of the database to use.\n    username: The user name used to authenticate.\n    password: The password used to authenticate.\n    host: The host address of the database.\n    port: The port to connect to the database.\n    query: A dictionary of string keys to string values to be passed to the dialect\n        and/or the DBAPI upon connect.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
					},
					required: ["driver", "database"],
				},
				SqlAlchemyConnector: {
					title: "SqlAlchemyConnector",
					description:
						"Block used to manage authentication with a database.\n\nUpon instantiating, an engine is created and maintained for the life of\nthe object until the close method is called.\n\nIt is recommended to use this block as a context manager, which will automatically\nclose the engine and its connections when the context is exited.\n\nIt is also recommended that this block is loaded and consumed within a single task\nor flow because if the block is passed across separate tasks and flows,\nthe state of the block's connection and cursor could be lost.",
					type: "object",
					properties: {
						connection_info: {
							title: "Connection Info",
							description:
								"SQLAlchemy URL to create the engine; either create from components or create from a string.",
							anyOf: [
								{
									$ref: "#/definitions/ConnectionComponents",
								},
								{
									type: "string",
									minLength: 1,
									maxLength: 65536,
									format: "uri",
								},
							],
						},
						connect_args: {
							title: "Additional Connection Arguments",
							description:
								"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
							type: "object",
						},
						fetch_size: {
							title: "Fetch Size",
							description: "The number of rows to fetch at a time.",
							default: 1,
							type: "integer",
						},
					},
					required: ["connection_info"],
					block_type_slug: "sqlalchemy-connector",
					secret_fields: ["connection_info.password"],
					block_schema_references: {},
				},
				DatabaseCredentials: {
					title: "DatabaseCredentials",
					description: "Block used to manage authentication with a database.",
					type: "object",
					properties: {
						driver: {
							title: "Driver",
							description: "The driver name to use.",
							anyOf: [
								{
									$ref: "#/definitions/AsyncDriver",
								},
								{
									$ref: "#/definitions/SyncDriver",
								},
								{
									type: "string",
								},
							],
						},
						username: {
							title: "Username",
							description: "The user name used to authenticate.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password used to authenticate.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						database: {
							title: "Database",
							description: "The name of the database to use.",
							type: "string",
						},
						host: {
							title: "Host",
							description: "The host address of the database.",
							type: "string",
						},
						port: {
							title: "Port",
							description: "The port to connect to the database.",
							type: "string",
						},
						query: {
							title: "Query",
							description:
								"A dictionary of string keys to string values to be passed to the dialect and/or the DBAPI upon connect. To specify non-string parameters to a Python DBAPI directly, use connect_args.",
							type: "object",
							additionalProperties: {
								type: "string",
							},
						},
						url: {
							title: "Url",
							description:
								"Manually create and provide a URL to create the engine, this is useful for external dialects, e.g. Snowflake, because some of the params, such as 'warehouse', is not directly supported in the vanilla `sqlalchemy.engine.URL.create` method; do not provide this alongside with other URL params as it will raise a `ValueError`.",
							minLength: 1,
							maxLength: 65536,
							format: "uri",
							type: "string",
						},
						connect_args: {
							title: "Connect Args",
							description:
								"The options which will be passed directly to the DBAPI's connect() method as additional keyword arguments.",
							type: "object",
						},
					},
					block_type_slug: "database-credentials",
					secret_fields: ["password"],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				credentials: [
					{
						block_schema_checksum:
							"sha256:01e6c0bdaac125860811b201f5a5e98ffefd5f8a49f1398b6996aec362643acc",
						block_type_slug: "sqlalchemy-connector",
					},
					{
						block_schema_checksum:
							"sha256:64175f83f2ae15bef7893a4d9a02658f2b5288747d54594ca6d356dc42e9993c",
						block_type_slug: "database-credentials",
					},
				],
			},
		},
		block_type_id: "5bf026cb-0066-4aab-829f-0726fca5da45",
		block_type: {
			id: "5bf026cb-0066-4aab-829f-0726fca5da45",
			created: "2024-12-02T18:19:08.054808Z",
			updated: "2024-12-02T18:19:08.054809Z",
			name: "dbt CLI Postgres Target Configs",
			slug: "dbt-cli-postgres-target-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/postgres/#prefect_dbt.cli.configs.postgres.PostgresTargetConfigs",
			description:
				"dbt CLI target configs containing credentials and settings specific to Postgres. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored PostgresTargetConfigs:\n```python\nfrom prefect_dbt.cli.configs import PostgresTargetConfigs\n\npostgres_target_configs = PostgresTargetConfigs.load("BLOCK_NAME")\n```\n\nInstantiate PostgresTargetConfigs with DatabaseCredentials.\n```python\nfrom prefect_dbt.cli.configs import PostgresTargetConfigs\nfrom prefect_sqlalchemy import DatabaseCredentials, SyncDriver\n\ncredentials = DatabaseCredentials(\n    driver=SyncDriver.POSTGRESQL_PSYCOPG2,\n    username="prefect",\n    password="prefect_password",\n    database="postgres",\n    host="host",\n    port=8080\n)\ntarget_configs = PostgresTargetConfigs(credentials=credentials, schema="schema")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "6e68d18e-16e4-4411-9a62-195e1d56695e",
		created: "2024-12-02T18:19:08.124205Z",
		updated: "2024-12-02T18:19:08.124206Z",
		checksum:
			"sha256:63df9d18a1aafde1cc8330cd49f81f6600b4ce6db92955973bbf341cc86e916d",
		fields: {
			title: "GlobalConfigs",
			description:
				"Global configs control things like the visual output\nof logs, the manner in which dbt parses your project,\nand what to do when dbt finds a version mismatch\nor a failing model. Docs can be found [here](\nhttps://docs.getdbt.com/reference/global-configs).",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				send_anonymous_usage_stats: {
					title: "Send Anonymous Usage Stats",
					description: "Whether usage stats are sent to dbt.",
					type: "boolean",
				},
				use_colors: {
					title: "Use Colors",
					description: "Colorize the output it prints in your terminal.",
					type: "boolean",
				},
				partial_parse: {
					title: "Partial Parse",
					description:
						"When partial parsing is enabled, dbt will use an stored internal manifest to determine which files have been changed (if any) since it last parsed the project.",
					type: "boolean",
				},
				printer_width: {
					title: "Printer Width",
					description: "Length of characters before starting a new line.",
					type: "integer",
				},
				write_json: {
					title: "Write Json",
					description:
						"Determines whether dbt writes JSON artifacts to the target/ directory.",
					type: "boolean",
				},
				warn_error: {
					title: "Warn Error",
					description: "Whether to convert dbt warnings into errors.",
					type: "boolean",
				},
				log_format: {
					title: "Log Format",
					description:
						"The LOG_FORMAT config specifies how dbt's logs should be formatted. If the value of this config is json, dbt will output fully structured logs in JSON format.",
					type: "string",
				},
				debug: {
					title: "Debug",
					description: "Whether to redirect dbt's debug logs to standard out.",
					type: "boolean",
				},
				version_check: {
					title: "Version Check",
					description:
						"Whether to raise an error if a project's version is used with an incompatible dbt version.",
					type: "boolean",
				},
				fail_fast: {
					title: "Fail Fast",
					description:
						"Make dbt exit immediately if a single resource fails to build.",
					type: "boolean",
				},
				use_experimental_parser: {
					title: "Use Experimental Parser",
					description:
						"Opt into the latest experimental version of the static parser.",
					type: "boolean",
				},
				static_parser: {
					title: "Static Parser",
					description:
						"Whether to use the [static parser](https://docs.getdbt.com/reference/parsing#static-parser).",
					type: "boolean",
				},
			},
			block_type_slug: "dbt-cli-global-configs",
			secret_fields: [],
			block_schema_references: {},
		},
		block_type_id: "2a678077-aebc-417f-be11-3eca095d349d",
		block_type: {
			id: "2a678077-aebc-417f-be11-3eca095d349d",
			created: "2024-12-02T18:19:08.054152Z",
			updated: "2024-12-02T18:19:08.054153Z",
			name: "dbt CLI Global Configs",
			slug: "dbt-cli-global-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/base/#prefect_dbt.cli.configs.base.GlobalConfigs",
			description:
				"Global configs control things like the visual output\nof logs, the manner in which dbt parses your project,\nand what to do when dbt finds a version mismatch\nor a failing model. Docs can be found [here](\nhttps://docs.getdbt.com/reference/global-configs). This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored GlobalConfigs:\n```python\nfrom prefect_dbt.cli.configs import GlobalConfigs\n\ndbt_cli_global_configs = GlobalConfigs.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "65a0abad-3ac2-4ee2-92dc-98b6a4c39058",
		created: "2024-12-02T18:19:08.121418Z",
		updated: "2024-12-02T18:19:08.121420Z",
		checksum:
			"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
		fields: {
			title: "GcpCredentials",
			description:
				"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
			type: "object",
			properties: {
				service_account_file: {
					title: "Service Account File",
					description: "Path to the service account JSON keyfile.",
					type: "string",
					format: "path",
				},
				service_account_info: {
					title: "Service Account Info",
					description: "The contents of the keyfile as a dict.",
					type: "object",
				},
				project: {
					title: "Project",
					description: "The GCP project to use for the client.",
					type: "string",
				},
			},
			block_type_slug: "gcp-credentials",
			secret_fields: ["service_account_info.*"],
			block_schema_references: {},
		},
		block_type_id: "a4119249-25c7-45e1-8bf7-4d36114ac4f1",
		block_type: {
			id: "a4119249-25c7-45e1-8bf7-4d36114ac4f1",
			created: "2024-12-02T18:19:08.061455Z",
			updated: "2024-12-02T18:19:08.061456Z",
			name: "GCP Credentials",
			slug: "gcp-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-gcp/credentials/#prefect_gcp.credentials.GcpCredentials",
			description:
				"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns. This block is part of the prefect-gcp collection. Install prefect-gcp with `pip install prefect-gcp` to use this block.",
			code_example:
				'Load GCP credentials stored in a `GCP Credentials` Block:\n```python\nfrom prefect_gcp import GcpCredentials\ngcp_credentials_block = GcpCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "4653f116-825c-4dc2-9253-0435d1c5966f",
		created: "2024-12-02T18:19:08.119121Z",
		updated: "2024-12-02T18:19:08.119122Z",
		checksum:
			"sha256:842c5dc7d4d1557eedff36982eafeda7b0803915942f72224a7f627efdbe5ff5",
		fields: {
			title: "BigQueryTargetConfigs",
			description:
				"dbt CLI target configs containing credentials and settings, specific to BigQuery.",
			type: "object",
			properties: {
				extras: {
					title: "Extras",
					description:
						"Extra target configs' keywords, not yet exposed in prefect-dbt, but available in dbt.",
					type: "object",
				},
				allow_field_overrides: {
					title: "Allow Field Overrides",
					description:
						"If enabled, fields from dbt target configs will override fields provided in extras and credentials.",
					default: false,
					type: "boolean",
				},
				type: {
					title: "Type",
					description: "The type of target.",
					default: "bigquery",
					enum: ["bigquery"],
					type: "string",
				},
				schema: {
					title: "Schema",
					description:
						"The schema that dbt will build objects into; in BigQuery, a schema is actually a dataset.",
					type: "string",
				},
				threads: {
					title: "Threads",
					description:
						"The number of threads representing the max number of paths through the graph dbt may work on at once.",
					default: 4,
					type: "integer",
				},
				project: {
					title: "Project",
					description: "The project to use.",
					type: "string",
				},
				credentials: {
					title: "Credentials",
					description: "The credentials to use to authenticate.",
					allOf: [
						{
							$ref: "#/definitions/GcpCredentials",
						},
					],
				},
			},
			required: ["schema"],
			block_type_slug: "dbt-cli-bigquery-target-configs",
			secret_fields: ["credentials.service_account_info.*"],
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:f764f9c506a2bed9e5ed7cc9083d06d95f13c01c8c9a9e45bae5d9b4dc522624",
					block_type_slug: "gcp-credentials",
				},
			},
			definitions: {
				GcpCredentials: {
					title: "GcpCredentials",
					description:
						"Block used to manage authentication with GCP. Google authentication is\nhandled via the `google.oauth2` module or through the CLI.\nSpecify either one of service `account_file` or `service_account_info`; if both\nare not specified, the client will try to detect the credentials following Google's\n[Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).\nSee Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)\nfor details on inference and recommended authentication patterns.",
					type: "object",
					properties: {
						service_account_file: {
							title: "Service Account File",
							description: "Path to the service account JSON keyfile.",
							type: "string",
							format: "path",
						},
						service_account_info: {
							title: "Service Account Info",
							description: "The contents of the keyfile as a dict.",
							type: "object",
						},
						project: {
							title: "Project",
							description: "The GCP project to use for the client.",
							type: "string",
						},
					},
					block_type_slug: "gcp-credentials",
					secret_fields: ["service_account_info.*"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "68b8a0b8-2ff1-4846-958d-da2f76cc3444",
		block_type: {
			id: "68b8a0b8-2ff1-4846-958d-da2f76cc3444",
			created: "2024-12-02T18:19:08.053488Z",
			updated: "2024-12-02T18:19:08.053489Z",
			name: "dbt CLI BigQuery Target Configs",
			slug: "dbt-cli-bigquery-target-configs",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1f4742f3473da5a9fc873430a803bb739e5e48a6-400x400.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-dbt/cli/configs/bigquery/#prefect_dbt.cli.configs.bigquery.BigQueryTargetConfigs",
			description:
				"dbt CLI target configs containing credentials and settings, specific to BigQuery. This block is part of the prefect-dbt collection. Install prefect-dbt with `pip install prefect-dbt` to use this block.",
			code_example:
				'Load stored BigQueryTargetConfigs.\n```python\nfrom prefect_dbt.cli.configs import BigQueryTargetConfigs\n\nbigquery_target_configs = BigQueryTargetConfigs.load("BLOCK_NAME")\n```\n\nInstantiate BigQueryTargetConfigs.\n```python\nfrom prefect_dbt.cli.configs import BigQueryTargetConfigs\nfrom prefect_gcp.credentials import GcpCredentials\n\ncredentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")\ntarget_configs = BigQueryTargetConfigs(\n    schema="schema",  # also known as dataset\n    credentials=credentials,\n)\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.1",
	},
	{
		id: "86d068f3-3028-48f6-8454-eb6aab9c7b28",
		created: "2024-12-02T18:19:08.117037Z",
		updated: "2024-12-02T18:19:08.117038Z",
		checksum:
			"sha256:58bae1446ee7a01ec90d15cf756f8acc221329e3b3580b077b508ff0f2425e35",
		fields: {
			title: "DatabricksCredentials",
			description: "Block used to manage Databricks authentication.",
			type: "object",
			properties: {
				databricks_instance: {
					title: "Databricks Instance",
					description:
						"Databricks instance used in formatting the endpoint URL.",
					type: "string",
				},
				token: {
					title: "Token",
					description: "The token to authenticate with Databricks.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				client_kwargs: {
					title: "Client Kwargs",
					description: "Additional keyword arguments to pass to AsyncClient.",
					type: "object",
				},
			},
			required: ["databricks_instance", "token"],
			block_type_slug: "databricks-credentials",
			secret_fields: ["token"],
			block_schema_references: {},
		},
		block_type_id: "b476453e-0cf2-45e1-8a31-b3b1ae2a1430",
		block_type: {
			id: "b476453e-0cf2-45e1-8a31-b3b1ae2a1430",
			created: "2024-12-02T18:19:08.052849Z",
			updated: "2024-12-02T18:19:08.052850Z",
			name: "Databricks Credentials",
			slug: "databricks-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/ff9a2573c23954bedd27b0f420465a55b1a99dfd-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-databricks/credentials/#prefect_databricks.credentials.DatabricksCredentials",
			description:
				"Block used to manage Databricks authentication. This block is part of the prefect-databricks collection. Install prefect-databricks with `pip install prefect-databricks` to use this block.",
			code_example:
				'Load stored Databricks credentials:\n```python\nfrom prefect_databricks import DatabricksCredentials\ndatabricks_credentials_block = DatabricksCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.2.3",
	},
	{
		id: "d578834a-1386-4627-919c-a16e2b428dc3",
		created: "2024-12-02T18:19:08.112531Z",
		updated: "2024-12-02T18:19:08.112532Z",
		checksum:
			"sha256:b159a8f21358b694f13fb67b73f20bf3f8b74138940fc0f16ab08107e78d5237",
		fields: {
			title: "BitBucketRepository",
			description: "Interact with files stored in BitBucket repositories.",
			type: "object",
			properties: {
				repository: {
					title: "Repository",
					description:
						"The URL of a BitBucket repository to read from in HTTPS format",
					type: "string",
				},
				reference: {
					title: "Reference",
					description:
						"An optional reference to pin to; can be a branch or tag.",
					type: "string",
				},
				bitbucket_credentials: {
					title: "Bitbucket Credentials",
					description:
						"An optional BitBucketCredentials block for authenticating with private BitBucket repos.",
					allOf: [
						{
							$ref: "#/definitions/BitBucketCredentials",
						},
					],
				},
			},
			required: ["repository"],
			block_type_slug: "bitbucket-repository",
			secret_fields: [
				"bitbucket_credentials.token",
				"bitbucket_credentials.password",
			],
			block_schema_references: {
				bitbucket_credentials: {
					block_schema_checksum:
						"sha256:ef96bdc56cde651f152e3f8938018d53d725b25b5ae98777872c0962250ba0fc",
					block_type_slug: "bitbucket-credentials",
				},
			},
			definitions: {
				BitBucketCredentials: {
					title: "BitBucketCredentials",
					description:
						"Store BitBucket credentials to interact with private BitBucket repositories.",
					type: "object",
					properties: {
						token: {
							title: "Token",
							description:
								"A BitBucket Personal Access Token - required for private repositories.",
							name: "Personal Access Token",
							example: "x-token-auth:my-token",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						username: {
							title: "Username",
							description:
								"Identification name unique across entire BitBucket site.",
							type: "string",
						},
						password: {
							title: "Password",
							description: "The password to authenticate to BitBucket.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						url: {
							title: "URL",
							description: "The base URL of your BitBucket instance.",
							default: "https://api.bitbucket.org/",
							type: "string",
						},
					},
					block_type_slug: "bitbucket-credentials",
					secret_fields: ["token", "password"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "2175b8e1-a817-48c2-b799-abbfa9a4b7a0",
		block_type: {
			id: "2175b8e1-a817-48c2-b799-abbfa9a4b7a0",
			created: "2024-12-02T18:19:08.052181Z",
			updated: "2024-12-02T18:19:08.052183Z",
			name: "BitBucket Repository",
			slug: "bitbucket-repository",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/5d729f7355fb6828c4b605268ded9cfafab3ae4f-250x250.png",
			documentation_url: null,
			description:
				"Interact with files stored in BitBucket repositories. This block is part of the prefect-bitbucket collection. Install prefect-bitbucket with `pip install prefect-bitbucket` to use this block.",
			code_example:
				'```python\nfrom prefect_bitbucket.repository import BitBucketRepository\n\nbitbucket_repository_block = BitBucketRepository.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["get-directory"],
		version: "0.2.2",
	},
	{
		id: "97a243b0-0e9b-467a-a40a-7e61517c3d87",
		created: "2024-12-02T18:19:08.110396Z",
		updated: "2024-12-02T18:19:08.110398Z",
		checksum:
			"sha256:ef96bdc56cde651f152e3f8938018d53d725b25b5ae98777872c0962250ba0fc",
		fields: {
			title: "BitBucketCredentials",
			description:
				"Store BitBucket credentials to interact with private BitBucket repositories.",
			type: "object",
			properties: {
				token: {
					title: "Token",
					description:
						"A BitBucket Personal Access Token - required for private repositories.",
					name: "Personal Access Token",
					example: "x-token-auth:my-token",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				username: {
					title: "Username",
					description:
						"Identification name unique across entire BitBucket site.",
					type: "string",
				},
				password: {
					title: "Password",
					description: "The password to authenticate to BitBucket.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				url: {
					title: "URL",
					description: "The base URL of your BitBucket instance.",
					default: "https://api.bitbucket.org/",
					type: "string",
				},
			},
			block_type_slug: "bitbucket-credentials",
			secret_fields: ["token", "password"],
			block_schema_references: {},
		},
		block_type_id: "34d40fae-8557-41ba-8d01-6c8386958f24",
		block_type: {
			id: "34d40fae-8557-41ba-8d01-6c8386958f24",
			created: "2024-12-02T18:19:08.051499Z",
			updated: "2024-12-02T18:19:08.051500Z",
			name: "BitBucket Credentials",
			slug: "bitbucket-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/5d729f7355fb6828c4b605268ded9cfafab3ae4f-250x250.png",
			documentation_url: null,
			description:
				"Store BitBucket credentials to interact with private BitBucket repositories. This block is part of the prefect-bitbucket collection. Install prefect-bitbucket with `pip install prefect-bitbucket` to use this block.",
			code_example:
				'Load stored BitBucket credentials:\n```python\nfrom prefect_bitbucket import BitBucketCredentials\nbitbucket_credentials_block = BitBucketCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.2.2",
	},
	{
		id: "5d86f8e9-80e4-4aab-a4a0-064d175bd81f",
		created: "2024-12-02T18:19:08.108233Z",
		updated: "2024-12-02T18:19:08.108234Z",
		checksum:
			"sha256:11338ccb5cd90992ac378f9b7a73cbf1942fae58343ac2026b3718ed688b52e6",
		fields: {
			title: "AzureMlCredentials",
			description:
				"Block used to manage authentication with AzureML. Azure authentication is\nhandled via the `azure` module.",
			type: "object",
			properties: {
				tenant_id: {
					title: "Tenant Id",
					description:
						"The active directory tenant that the service identity belongs to.",
					type: "string",
				},
				service_principal_id: {
					title: "Service Principal Id",
					description: "The service principal ID.",
					type: "string",
				},
				service_principal_password: {
					title: "Service Principal Password",
					description: "The service principal password/key.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				subscription_id: {
					title: "Subscription Id",
					description:
						"The Azure subscription ID containing the workspace, in format: '00000000-0000-0000-0000-000000000000'.",
					type: "string",
				},
				resource_group: {
					title: "Resource Group",
					description: "The resource group containing the workspace.",
					type: "string",
				},
				workspace_name: {
					title: "Workspace Name",
					description: "The existing workspace name.",
					type: "string",
				},
			},
			required: [
				"tenant_id",
				"service_principal_id",
				"service_principal_password",
				"subscription_id",
				"resource_group",
				"workspace_name",
			],
			block_type_slug: "azureml-credentials",
			secret_fields: ["service_principal_password"],
			block_schema_references: {},
		},
		block_type_id: "fa64978f-3653-4153-96db-eb26ff43719c",
		block_type: {
			id: "fa64978f-3653-4153-96db-eb26ff43719c",
			created: "2024-12-02T18:19:08.050852Z",
			updated: "2024-12-02T18:19:08.050854Z",
			name: "AzureML Credentials",
			slug: "azureml-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureMlCredentials",
			description:
				"Block used to manage authentication with AzureML. Azure authentication is\nhandled via the `azure` module. This block is part of the prefect-azure collection. Install prefect-azure with `pip install prefect-azure` to use this block.",
			code_example:
				'Load stored AzureML credentials:\n```python\nfrom prefect_azure import AzureMlCredentials\nazure_ml_credentials_block = AzureMlCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.3.7",
	},
	{
		id: "b3b50bc6-5812-43f8-a60c-69cfb525568a",
		created: "2024-12-02T18:19:08.106103Z",
		updated: "2024-12-02T18:19:08.106104Z",
		checksum:
			"sha256:2f9f6e6f6c2eb570a05113638e6237fe74f7684993a351018657211d4705a83a",
		fields: {
			title: "AzureCosmosDbCredentials",
			description:
				"Block used to manage Cosmos DB authentication with Azure.\nAzure authentication is handled via the `azure` module through\na connection string.",
			type: "object",
			properties: {
				connection_string: {
					title: "Connection String",
					description: "Includes the authorization information required.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
			},
			required: ["connection_string"],
			block_type_slug: "azure-cosmos-db-credentials",
			secret_fields: ["connection_string"],
			block_schema_references: {},
		},
		block_type_id: "c9675885-d288-4bf0-a261-375d64848d96",
		block_type: {
			id: "c9675885-d288-4bf0-a261-375d64848d96",
			created: "2024-12-02T18:19:08.050165Z",
			updated: "2024-12-02T18:19:08.050166Z",
			name: "Azure Cosmos DB Credentials",
			slug: "azure-cosmos-db-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureCosmosDbCredentials",
			description:
				"Block used to manage Cosmos DB authentication with Azure.\nAzure authentication is handled via the `azure` module through\na connection string. This block is part of the prefect-azure collection. Install prefect-azure with `pip install prefect-azure` to use this block.",
			code_example:
				'Load stored Azure Cosmos DB credentials:\n```python\nfrom prefect_azure import AzureCosmosDbCredentials\nazure_credentials_block = AzureCosmosDbCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.3.7",
	},
	{
		id: "1a45ceff-5435-4c9f-9983-e9a6f7a15897",
		created: "2024-12-02T18:19:08.103978Z",
		updated: "2024-12-02T18:19:08.103979Z",
		checksum:
			"sha256:17a9122f9f345a4547128cc05f7ff7146da9a72c4bac2850004fcc6c8d9be2d1",
		fields: {
			title: "AzureContainerInstanceCredentials",
			description:
				"Block used to manage Azure Container Instances authentication. Stores Azure Service\nPrincipal authentication data.",
			type: "object",
			properties: {
				client_id: {
					title: "Client ID",
					description:
						"The service principal client ID. If none of client_id, tenant_id, and client_secret are provided, will use DefaultAzureCredential; else will need to provide all three to use ClientSecretCredential.",
					type: "string",
				},
				tenant_id: {
					title: "Tenant ID",
					description:
						"The service principal tenant ID.If none of client_id, tenant_id, and client_secret are provided, will use DefaultAzureCredential; else will need to provide all three to use ClientSecretCredential.",
					type: "string",
				},
				client_secret: {
					title: "Client Secret",
					description:
						"The service principal client secret.If none of client_id, tenant_id, and client_secret are provided, will use DefaultAzureCredential; else will need to provide all three to use ClientSecretCredential.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				credential_kwargs: {
					title: "Additional Credential Keyword Arguments",
					description:
						"Additional keyword arguments to pass to `ClientSecretCredential` or `DefaultAzureCredential`.",
					type: "object",
				},
			},
			block_type_slug: "azure-container-instance-credentials",
			secret_fields: ["client_secret"],
			block_schema_references: {},
		},
		block_type_id: "8b351acd-687a-4c2e-8178-91d194336efe",
		block_type: {
			id: "8b351acd-687a-4c2e-8178-91d194336efe",
			created: "2024-12-02T18:19:08.049474Z",
			updated: "2024-12-02T18:19:08.049475Z",
			name: "Azure Container Instance Credentials",
			slug: "azure-container-instance-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureContainerInstanceCredentials",
			description:
				"Block used to manage Azure Container Instances authentication. Stores Azure Service\nPrincipal authentication data. This block is part of the prefect-azure collection. Install prefect-azure with `pip install prefect-azure` to use this block.",
			code_example:
				'```python\nfrom prefect_azure.credentials import AzureContainerInstanceCredentials\n\nazure_container_instance_credentials_block = AzureContainerInstanceCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.3.7",
	},
	{
		id: "0b0ab3b1-71b6-4e5b-8f67-6e363319663d",
		created: "2024-12-02T18:19:08.101880Z",
		updated: "2024-12-02T18:19:08.101882Z",
		checksum:
			"sha256:73e835b6cb9a1902fd869037fb7f8a90f974508dda7a168e748a1206e7c325eb",
		fields: {
			title: "AzureBlobStorageCredentials",
			description:
				"Stores credentials for authenticating with Azure Blob Storage.",
			type: "object",
			properties: {
				connection_string: {
					title: "Connection String",
					description:
						"The connection string to your Azure storage account. If provided, the connection string will take precedence over the account URL.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				account_url: {
					title: "Account URL",
					description:
						"The URL for your Azure storage account. If provided, the account URL will be used to authenticate with the discovered default Azure credentials.",
					type: "string",
				},
			},
			block_type_slug: "azure-blob-storage-credentials",
			secret_fields: ["connection_string"],
			block_schema_references: {},
		},
		block_type_id: "2ae8f661-629e-4fe4-8472-ddb6805f1111",
		block_type: {
			id: "2ae8f661-629e-4fe4-8472-ddb6805f1111",
			created: "2024-12-02T18:19:08.048836Z",
			updated: "2024-12-02T18:19:08.048838Z",
			name: "Azure Blob Storage Credentials",
			slug: "azure-blob-storage-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureBlobStorageCredentials",
			description:
				"Stores credentials for authenticating with Azure Blob Storage. This block is part of the prefect-azure collection. Install prefect-azure with `pip install prefect-azure` to use this block.",
			code_example:
				'Load stored Azure Blob Storage credentials and retrieve a blob service client:\n```python\nfrom prefect_azure import AzureBlobStorageCredentials\n\nazure_credentials_block = AzureBlobStorageCredentials.load("BLOCK_NAME")\n\nblob_service_client = azure_credentials_block.get_blob_client()\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.3.7",
	},
	{
		id: "d91c2e9c-0c7d-442a-94d0-47dcb1c54de4",
		created: "2024-12-02T18:19:08.099083Z",
		updated: "2024-12-02T18:19:08.099084Z",
		checksum:
			"sha256:73e835b6cb9a1902fd869037fb7f8a90f974508dda7a168e748a1206e7c325eb",
		fields: {
			title: "AzureBlobStorageCredentials",
			description:
				"Stores credentials for authenticating with Azure Blob Storage.",
			type: "object",
			properties: {
				connection_string: {
					title: "Connection String",
					description:
						"The connection string to your Azure storage account. If provided, the connection string will take precedence over the account URL.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				account_url: {
					title: "Account URL",
					description:
						"The URL for your Azure storage account. If provided, the account URL will be used to authenticate with the discovered default Azure credentials.",
					type: "string",
				},
			},
			block_type_slug: "azure-blob-storage-credentials",
			secret_fields: ["connection_string"],
			block_schema_references: {},
		},
		block_type_id: "2ae8f661-629e-4fe4-8472-ddb6805f1111",
		block_type: {
			id: "2ae8f661-629e-4fe4-8472-ddb6805f1111",
			created: "2024-12-02T18:19:08.048836Z",
			updated: "2024-12-02T18:19:08.048838Z",
			name: "Azure Blob Storage Credentials",
			slug: "azure-blob-storage-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureBlobStorageCredentials",
			description:
				"Stores credentials for authenticating with Azure Blob Storage. This block is part of the prefect-azure collection. Install prefect-azure with `pip install prefect-azure` to use this block.",
			code_example:
				'Load stored Azure Blob Storage credentials and retrieve a blob service client:\n```python\nfrom prefect_azure import AzureBlobStorageCredentials\n\nazure_credentials_block = AzureBlobStorageCredentials.load("BLOCK_NAME")\n\nblob_service_client = azure_credentials_block.get_blob_client()\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "non-versioned",
	},
	{
		id: "04a7ae13-39ca-4192-a9d9-ed045826336e",
		created: "2024-12-02T18:19:08.096715Z",
		updated: "2024-12-02T18:19:08.096717Z",
		checksum:
			"sha256:dcb604fba31292177868c0998110c7b4c0ba0b5601ee39679b2936adfd836f19",
		fields: {
			title: "AzureBlobStorageContainer",
			description:
				"Represents a container in Azure Blob Storage.\n\nThis class provides methods for downloading and uploading files and folders\nto and from the Azure Blob Storage container.",
			type: "object",
			properties: {
				container_name: {
					title: "Container Name",
					description: "The name of a Azure Blob Storage container.",
					type: "string",
				},
				credentials: {
					title: "Credentials",
					description: "The credentials to use for authentication with Azure.",
					allOf: [
						{
							$ref: "#/definitions/AzureBlobStorageCredentials",
						},
					],
				},
				base_folder: {
					title: "Base Folder",
					description:
						"A base path to a folder within the container to use for reading and writing objects.",
					type: "string",
				},
			},
			required: ["container_name"],
			block_type_slug: "azure-blob-storage-container",
			secret_fields: ["credentials.connection_string"],
			block_schema_references: {
				credentials: {
					block_schema_checksum:
						"sha256:73e835b6cb9a1902fd869037fb7f8a90f974508dda7a168e748a1206e7c325eb",
					block_type_slug: "azure-blob-storage-credentials",
				},
			},
			definitions: {
				AzureBlobStorageCredentials: {
					title: "AzureBlobStorageCredentials",
					description:
						"Stores credentials for authenticating with Azure Blob Storage.",
					type: "object",
					properties: {
						connection_string: {
							title: "Connection String",
							description:
								"The connection string to your Azure storage account. If provided, the connection string will take precedence over the account URL.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						account_url: {
							title: "Account URL",
							description:
								"The URL for your Azure storage account. If provided, the account URL will be used to authenticate with the discovered default Azure credentials.",
							type: "string",
						},
					},
					block_type_slug: "azure-blob-storage-credentials",
					secret_fields: ["connection_string"],
					block_schema_references: {},
				},
			},
		},
		block_type_id: "de662ded-59e2-4147-9dc4-2895a495159f",
		block_type: {
			id: "de662ded-59e2-4147-9dc4-2895a495159f",
			created: "2024-12-02T18:19:08.048194Z",
			updated: "2024-12-02T18:19:08.048195Z",
			name: "Azure Blob Storage Container",
			slug: "azure-blob-storage-container",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-azure/blob_storage/#prefect_azure.blob_storabe.AzureBlobStorageContainer",
			description:
				"Represents a container in Azure Blob Storage.\n\nThis class provides methods for downloading and uploading files and folders\nto and from the Azure Blob Storage container. This block is part of the prefect-azure collection. Install prefect-azure with `pip install prefect-azure` to use this block.",
			code_example:
				'```python\nfrom prefect_azure.blob_storage import AzureBlobStorageContainer\n\nazure_blob_storage_container_block = AzureBlobStorageContainer.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["get-directory", "put-directory", "read-path", "write-path"],
		version: "0.3.7",
	},
	{
		id: "1c678b67-8c39-45f7-bd5b-2e80def53617",
		created: "2024-12-02T18:19:08.090580Z",
		updated: "2024-12-02T18:19:08.090582Z",
		checksum:
			"sha256:da1e638612365b12ec83b6102986cc5efe54e84b7144bd668629f6972afe748f",
		fields: {
			title: "S3Bucket",
			description:
				"Block used to store data using AWS S3 or S3-compatible object storage like MinIO.",
			type: "object",
			properties: {
				bucket_name: {
					title: "Bucket Name",
					description: "Name of your bucket.",
					type: "string",
				},
				credentials: {
					title: "Credentials",
					description: "A block containing your credentials to AWS or MinIO.",
					anyOf: [
						{
							$ref: "#/definitions/MinIOCredentials",
						},
						{
							$ref: "#/definitions/AwsCredentials",
						},
					],
				},
				bucket_folder: {
					title: "Bucket Folder",
					description:
						"A default path to a folder within the S3 bucket to use for reading and writing objects.",
					default: "",
					type: "string",
				},
			},
			required: ["bucket_name"],
			block_type_slug: "s3-bucket",
			secret_fields: [
				"credentials.minio_root_password",
				"credentials.aws_secret_access_key",
			],
			definitions: {
				AwsClientParameters: {
					title: "AwsClientParameters",
					description:
						'Model used to manage extra parameters that you can pass when you initialize\nthe Client. If you want to find more information, see\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html)\nfor more info about the possible client configurations.\n\nAttributes:\n    api_version: The API version to use. By default, botocore will\n        use the latest API version when creating a client. You only need\n        to specify this parameter if you want to use a previous API version\n        of the client.\n    use_ssl: Whether or not to use SSL. By default, SSL is used.\n        Note that not all services support non-ssl connections.\n    verify: Whether or not to verify SSL certificates. By default\n        SSL certificates are verified. If False, SSL will still be used\n        (unless use_ssl is False), but SSL certificates\n        will not be verified. Passing a file path to this is deprecated.\n    verify_cert_path: A filename of the CA cert bundle to\n        use. You can specify this argument if you want to use a\n        different CA cert bundle than the one used by botocore.\n    endpoint_url: The complete URL to use for the constructed\n        client. Normally, botocore will automatically construct the\n        appropriate URL to use when communicating with a service. You\n        can specify a complete URL (including the "http/https" scheme)\n        to override this behavior. If this value is provided,\n        then ``use_ssl`` is ignored.\n    config: Advanced configuration for Botocore clients. See\n        [botocore docs](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)\n        for more details.',
					type: "object",
					properties: {
						api_version: {
							title: "API Version",
							description: "The API version to use.",
							type: "string",
						},
						use_ssl: {
							title: "Use SSL",
							description: "Whether or not to use SSL.",
							default: true,
							type: "boolean",
						},
						verify: {
							title: "Verify",
							description: "Whether or not to verify SSL certificates.",
							default: true,
							anyOf: [
								{
									type: "boolean",
								},
								{
									type: "string",
									format: "file-path",
								},
							],
						},
						verify_cert_path: {
							title: "Certificate Authority Bundle File Path",
							description: "Path to the CA cert bundle to use.",
							format: "file-path",
							type: "string",
						},
						endpoint_url: {
							title: "Endpoint URL",
							description:
								"The complete URL to use for the constructed client.",
							type: "string",
						},
						config: {
							title: "Botocore Config",
							description: "Advanced configuration for Botocore clients.",
							type: "object",
						},
					},
				},
				AwsCredentials: {
					title: "AwsCredentials",
					description:
						"Block used to manage authentication with AWS. AWS authentication is\nhandled via the `boto3` module. Refer to the\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)\nfor more info about the possible credential configurations.",
					type: "object",
					properties: {
						aws_access_key_id: {
							title: "AWS Access Key ID",
							description: "A specific AWS access key ID.",
							type: "string",
						},
						aws_secret_access_key: {
							title: "AWS Access Key Secret",
							description: "A specific AWS secret access key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						aws_session_token: {
							title: "AWS Session Token",
							description:
								"The session key for your AWS account. This is only needed when you are using temporary credentials.",
							type: "string",
						},
						profile_name: {
							title: "Profile Name",
							description: "The profile to use when creating your session.",
							type: "string",
						},
						region_name: {
							title: "Region Name",
							description:
								"The AWS Region where you want to create new connections.",
							type: "string",
						},
						aws_client_parameters: {
							title: "AWS Client Parameters",
							description: "Extra parameters to initialize the Client.",
							allOf: [
								{
									$ref: "#/definitions/AwsClientParameters",
								},
							],
						},
					},
					block_type_slug: "aws-credentials",
					secret_fields: ["aws_secret_access_key"],
					block_schema_references: {},
				},
				MinIOCredentials: {
					title: "MinIOCredentials",
					description:
						"Block used to manage authentication with MinIO. Refer to the MinIO docs: https://docs.min.io/docs/minio-server-configuration-guide.html for more info about the possible credential configurations.",
					type: "object",
					properties: {
						minio_root_user: {
							title: "Minio Root User",
							description: "Admin or root user.",
							type: "string",
						},
						minio_root_password: {
							title: "Minio Root Password",
							description: "Admin or root password.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						region_name: {
							title: "Region Name",
							description:
								"The AWS Region where you want to create new connections.",
							type: "string",
						},
						aws_client_parameters: {
							title: "Aws Client Parameters",
							description: "Extra parameters to initialize the Client.",
							allOf: [
								{
									$ref: "#/definitions/AwsClientParameters",
								},
							],
						},
					},
					required: ["minio_root_user", "minio_root_password"],
					block_type_slug: "minio-credentials",
					secret_fields: ["minio_root_password"],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				credentials: [
					{
						block_schema_checksum:
							"sha256:17b73297ed60f080fb235b3a5a145a6d9b28a09b3ff2d9d17810b5e2c2075ebe",
						block_type_slug: "aws-credentials",
					},
					{
						block_schema_checksum:
							"sha256:5b4f1e5270f3a3670ff3d06b7e6e8246d54dacba976321dec42abe51c33415fb",
						block_type_slug: "minio-credentials",
					},
				],
			},
		},
		block_type_id: "e04607dc-ba1f-4710-8f8c-b0bab6af661e",
		block_type: {
			id: "e04607dc-ba1f-4710-8f8c-b0bab6af661e",
			created: "2024-12-02T18:19:08.047535Z",
			updated: "2024-12-02T18:19:08.047537Z",
			name: "S3 Bucket",
			slug: "s3-bucket",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-aws/s3/#prefect_aws.s3.S3Bucket",
			description:
				"Block used to store data using AWS S3 or S3-compatible object storage like MinIO. This block is part of the prefect-aws collection. Install prefect-aws with `pip install prefect-aws` to use this block.",
			code_example:
				'```python\nfrom prefect_aws.s3 import S3Bucket\n\ns3_bucket_block = S3Bucket.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["get-directory", "put-directory", "read-path", "write-path"],
		version: "0.4.14",
	},
	{
		id: "15bad625-725f-4c32-a9ff-be76aa8d7dd1",
		created: "2024-12-02T18:19:08.088337Z",
		updated: "2024-12-02T18:19:08.088339Z",
		checksum:
			"sha256:5b4f1e5270f3a3670ff3d06b7e6e8246d54dacba976321dec42abe51c33415fb",
		fields: {
			title: "MinIOCredentials",
			description:
				"Block used to manage authentication with MinIO. Refer to the MinIO docs: https://docs.min.io/docs/minio-server-configuration-guide.html for more info about the possible credential configurations.",
			type: "object",
			properties: {
				minio_root_user: {
					title: "Minio Root User",
					description: "Admin or root user.",
					type: "string",
				},
				minio_root_password: {
					title: "Minio Root Password",
					description: "Admin or root password.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				region_name: {
					title: "Region Name",
					description:
						"The AWS Region where you want to create new connections.",
					type: "string",
				},
				aws_client_parameters: {
					title: "Aws Client Parameters",
					description: "Extra parameters to initialize the Client.",
					allOf: [
						{
							$ref: "#/definitions/AwsClientParameters",
						},
					],
				},
			},
			required: ["minio_root_user", "minio_root_password"],
			block_type_slug: "minio-credentials",
			secret_fields: ["minio_root_password"],
			definitions: {
				AwsClientParameters: {
					title: "AwsClientParameters",
					description:
						'Model used to manage extra parameters that you can pass when you initialize\nthe Client. If you want to find more information, see\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html)\nfor more info about the possible client configurations.\n\nAttributes:\n    api_version: The API version to use. By default, botocore will\n        use the latest API version when creating a client. You only need\n        to specify this parameter if you want to use a previous API version\n        of the client.\n    use_ssl: Whether or not to use SSL. By default, SSL is used.\n        Note that not all services support non-ssl connections.\n    verify: Whether or not to verify SSL certificates. By default\n        SSL certificates are verified. If False, SSL will still be used\n        (unless use_ssl is False), but SSL certificates\n        will not be verified. Passing a file path to this is deprecated.\n    verify_cert_path: A filename of the CA cert bundle to\n        use. You can specify this argument if you want to use a\n        different CA cert bundle than the one used by botocore.\n    endpoint_url: The complete URL to use for the constructed\n        client. Normally, botocore will automatically construct the\n        appropriate URL to use when communicating with a service. You\n        can specify a complete URL (including the "http/https" scheme)\n        to override this behavior. If this value is provided,\n        then ``use_ssl`` is ignored.\n    config: Advanced configuration for Botocore clients. See\n        [botocore docs](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)\n        for more details.',
					type: "object",
					properties: {
						api_version: {
							title: "API Version",
							description: "The API version to use.",
							type: "string",
						},
						use_ssl: {
							title: "Use SSL",
							description: "Whether or not to use SSL.",
							default: true,
							type: "boolean",
						},
						verify: {
							title: "Verify",
							description: "Whether or not to verify SSL certificates.",
							default: true,
							anyOf: [
								{
									type: "boolean",
								},
								{
									type: "string",
									format: "file-path",
								},
							],
						},
						verify_cert_path: {
							title: "Certificate Authority Bundle File Path",
							description: "Path to the CA cert bundle to use.",
							format: "file-path",
							type: "string",
						},
						endpoint_url: {
							title: "Endpoint URL",
							description:
								"The complete URL to use for the constructed client.",
							type: "string",
						},
						config: {
							title: "Botocore Config",
							description: "Advanced configuration for Botocore clients.",
							type: "object",
						},
					},
				},
			},
			block_schema_references: {},
		},
		block_type_id: "89d1453f-19b3-4ccb-83c3-0b874048c6d3",
		block_type: {
			id: "89d1453f-19b3-4ccb-83c3-0b874048c6d3",
			created: "2024-12-02T18:19:08.046811Z",
			updated: "2024-12-02T18:19:08.046813Z",
			name: "MinIO Credentials",
			slug: "minio-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/676cb17bcbdff601f97e0a02ff8bcb480e91ff40-250x250.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.MinIOCredentials",
			description:
				"Block used to manage authentication with MinIO. Refer to the MinIO docs: https://docs.min.io/docs/minio-server-configuration-guide.html for more info about the possible credential configurations. This block is part of the prefect-aws collection. Install prefect-aws with `pip install prefect-aws` to use this block.",
			code_example:
				'Load stored MinIO credentials:\n```python\nfrom prefect_aws import MinIOCredentials\n\nminio_credentials_block = MinIOCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.14",
	},
	{
		id: "1d8ba89b-c9a8-4074-8cdd-399fdf2648e0",
		created: "2024-12-02T18:19:08.083488Z",
		updated: "2024-12-02T18:19:08.083489Z",
		checksum:
			"sha256:93fb424309b85c0ef9a8e69cc9d0df1e0afa0f2ed15f1ecc710ec3463513b2e4",
		fields: {
			title: "LambdaFunction",
			description:
				"Invoke a Lambda function. This block is part of the prefect-aws\ncollection. Install prefect-aws with `pip install prefect-aws` to use this\nblock.",
			type: "object",
			properties: {
				function_name: {
					title: "Function Name",
					description:
						"The name, ARN, or partial ARN of the Lambda function to run. This must be the name of a function that is already deployed to AWS Lambda.",
					type: "string",
				},
				qualifier: {
					title: "Qualifier",
					description:
						"The version or alias of the Lambda function to use when invoked. If not specified, the latest (unqualified) version of the Lambda function will be used.",
					type: "string",
				},
				aws_credentials: {
					title: "AWS Credentials",
					description: "The AWS credentials to invoke the Lambda with.",
					allOf: [
						{
							$ref: "#/definitions/AwsCredentials",
						},
					],
				},
			},
			required: ["function_name"],
			block_type_slug: "lambda-function",
			secret_fields: ["aws_credentials.aws_secret_access_key"],
			definitions: {
				AwsClientParameters: {
					title: "AwsClientParameters",
					description:
						'Model used to manage extra parameters that you can pass when you initialize\nthe Client. If you want to find more information, see\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html)\nfor more info about the possible client configurations.\n\nAttributes:\n    api_version: The API version to use. By default, botocore will\n        use the latest API version when creating a client. You only need\n        to specify this parameter if you want to use a previous API version\n        of the client.\n    use_ssl: Whether or not to use SSL. By default, SSL is used.\n        Note that not all services support non-ssl connections.\n    verify: Whether or not to verify SSL certificates. By default\n        SSL certificates are verified. If False, SSL will still be used\n        (unless use_ssl is False), but SSL certificates\n        will not be verified. Passing a file path to this is deprecated.\n    verify_cert_path: A filename of the CA cert bundle to\n        use. You can specify this argument if you want to use a\n        different CA cert bundle than the one used by botocore.\n    endpoint_url: The complete URL to use for the constructed\n        client. Normally, botocore will automatically construct the\n        appropriate URL to use when communicating with a service. You\n        can specify a complete URL (including the "http/https" scheme)\n        to override this behavior. If this value is provided,\n        then ``use_ssl`` is ignored.\n    config: Advanced configuration for Botocore clients. See\n        [botocore docs](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)\n        for more details.',
					type: "object",
					properties: {
						api_version: {
							title: "API Version",
							description: "The API version to use.",
							type: "string",
						},
						use_ssl: {
							title: "Use SSL",
							description: "Whether or not to use SSL.",
							default: true,
							type: "boolean",
						},
						verify: {
							title: "Verify",
							description: "Whether or not to verify SSL certificates.",
							default: true,
							anyOf: [
								{
									type: "boolean",
								},
								{
									type: "string",
									format: "file-path",
								},
							],
						},
						verify_cert_path: {
							title: "Certificate Authority Bundle File Path",
							description: "Path to the CA cert bundle to use.",
							format: "file-path",
							type: "string",
						},
						endpoint_url: {
							title: "Endpoint URL",
							description:
								"The complete URL to use for the constructed client.",
							type: "string",
						},
						config: {
							title: "Botocore Config",
							description: "Advanced configuration for Botocore clients.",
							type: "object",
						},
					},
				},
				AwsCredentials: {
					title: "AwsCredentials",
					description:
						"Block used to manage authentication with AWS. AWS authentication is\nhandled via the `boto3` module. Refer to the\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)\nfor more info about the possible credential configurations.",
					type: "object",
					properties: {
						aws_access_key_id: {
							title: "AWS Access Key ID",
							description: "A specific AWS access key ID.",
							type: "string",
						},
						aws_secret_access_key: {
							title: "AWS Access Key Secret",
							description: "A specific AWS secret access key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						aws_session_token: {
							title: "AWS Session Token",
							description:
								"The session key for your AWS account. This is only needed when you are using temporary credentials.",
							type: "string",
						},
						profile_name: {
							title: "Profile Name",
							description: "The profile to use when creating your session.",
							type: "string",
						},
						region_name: {
							title: "Region Name",
							description:
								"The AWS Region where you want to create new connections.",
							type: "string",
						},
						aws_client_parameters: {
							title: "AWS Client Parameters",
							description: "Extra parameters to initialize the Client.",
							allOf: [
								{
									$ref: "#/definitions/AwsClientParameters",
								},
							],
						},
					},
					block_type_slug: "aws-credentials",
					secret_fields: ["aws_secret_access_key"],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				aws_credentials: {
					block_schema_checksum:
						"sha256:17b73297ed60f080fb235b3a5a145a6d9b28a09b3ff2d9d17810b5e2c2075ebe",
					block_type_slug: "aws-credentials",
				},
			},
		},
		block_type_id: "1e2effc6-e0d3-4098-9498-c8777ef8a67a",
		block_type: {
			id: "1e2effc6-e0d3-4098-9498-c8777ef8a67a",
			created: "2024-12-02T18:19:08.046102Z",
			updated: "2024-12-02T18:19:08.046104Z",
			name: "Lambda Function",
			slug: "lambda-function",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-aws/s3/#prefect_aws.lambda_function.LambdaFunction",
			description:
				"Invoke a Lambda function. This block is part of the prefect-aws\ncollection. Install prefect-aws with `pip install prefect-aws` to use this\nblock. This block is part of the prefect-aws collection. Install prefect-aws with `pip install prefect-aws` to use this block.",
			code_example:
				'```python\nfrom prefect_aws.lambda_function import LambdaFunction\n\nlambda_function_block = LambdaFunction.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.14",
	},
	{
		id: "d234fee7-7d97-4507-b306-a721712edb2f",
		created: "2024-12-02T18:19:08.077859Z",
		updated: "2024-12-02T18:19:08.077860Z",
		checksum:
			"sha256:d10fde5ac25b10edca4859c4d0bf61b4a9106215cd79ab80997f29859b190b7d",
		fields: {
			title: "AwsSecret",
			description: "Manages a secret in AWS's Secrets Manager.",
			type: "object",
			properties: {
				aws_credentials: {
					$ref: "#/definitions/AwsCredentials",
				},
				secret_name: {
					title: "Secret Name",
					description: "The name of the secret.",
					type: "string",
				},
			},
			required: ["aws_credentials", "secret_name"],
			block_type_slug: "aws-secret",
			secret_fields: ["aws_credentials.aws_secret_access_key"],
			definitions: {
				AwsClientParameters: {
					title: "AwsClientParameters",
					description:
						'Model used to manage extra parameters that you can pass when you initialize\nthe Client. If you want to find more information, see\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html)\nfor more info about the possible client configurations.\n\nAttributes:\n    api_version: The API version to use. By default, botocore will\n        use the latest API version when creating a client. You only need\n        to specify this parameter if you want to use a previous API version\n        of the client.\n    use_ssl: Whether or not to use SSL. By default, SSL is used.\n        Note that not all services support non-ssl connections.\n    verify: Whether or not to verify SSL certificates. By default\n        SSL certificates are verified. If False, SSL will still be used\n        (unless use_ssl is False), but SSL certificates\n        will not be verified. Passing a file path to this is deprecated.\n    verify_cert_path: A filename of the CA cert bundle to\n        use. You can specify this argument if you want to use a\n        different CA cert bundle than the one used by botocore.\n    endpoint_url: The complete URL to use for the constructed\n        client. Normally, botocore will automatically construct the\n        appropriate URL to use when communicating with a service. You\n        can specify a complete URL (including the "http/https" scheme)\n        to override this behavior. If this value is provided,\n        then ``use_ssl`` is ignored.\n    config: Advanced configuration for Botocore clients. See\n        [botocore docs](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)\n        for more details.',
					type: "object",
					properties: {
						api_version: {
							title: "API Version",
							description: "The API version to use.",
							type: "string",
						},
						use_ssl: {
							title: "Use SSL",
							description: "Whether or not to use SSL.",
							default: true,
							type: "boolean",
						},
						verify: {
							title: "Verify",
							description: "Whether or not to verify SSL certificates.",
							default: true,
							anyOf: [
								{
									type: "boolean",
								},
								{
									type: "string",
									format: "file-path",
								},
							],
						},
						verify_cert_path: {
							title: "Certificate Authority Bundle File Path",
							description: "Path to the CA cert bundle to use.",
							format: "file-path",
							type: "string",
						},
						endpoint_url: {
							title: "Endpoint URL",
							description:
								"The complete URL to use for the constructed client.",
							type: "string",
						},
						config: {
							title: "Botocore Config",
							description: "Advanced configuration for Botocore clients.",
							type: "object",
						},
					},
				},
				AwsCredentials: {
					title: "AwsCredentials",
					description:
						"Block used to manage authentication with AWS. AWS authentication is\nhandled via the `boto3` module. Refer to the\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)\nfor more info about the possible credential configurations.",
					type: "object",
					properties: {
						aws_access_key_id: {
							title: "AWS Access Key ID",
							description: "A specific AWS access key ID.",
							type: "string",
						},
						aws_secret_access_key: {
							title: "AWS Access Key Secret",
							description: "A specific AWS secret access key.",
							type: "string",
							writeOnly: true,
							format: "password",
						},
						aws_session_token: {
							title: "AWS Session Token",
							description:
								"The session key for your AWS account. This is only needed when you are using temporary credentials.",
							type: "string",
						},
						profile_name: {
							title: "Profile Name",
							description: "The profile to use when creating your session.",
							type: "string",
						},
						region_name: {
							title: "Region Name",
							description:
								"The AWS Region where you want to create new connections.",
							type: "string",
						},
						aws_client_parameters: {
							title: "AWS Client Parameters",
							description: "Extra parameters to initialize the Client.",
							allOf: [
								{
									$ref: "#/definitions/AwsClientParameters",
								},
							],
						},
					},
					block_type_slug: "aws-credentials",
					secret_fields: ["aws_secret_access_key"],
					block_schema_references: {},
				},
			},
			block_schema_references: {
				aws_credentials: {
					block_schema_checksum:
						"sha256:17b73297ed60f080fb235b3a5a145a6d9b28a09b3ff2d9d17810b5e2c2075ebe",
					block_type_slug: "aws-credentials",
				},
			},
		},
		block_type_id: "52d6b05e-a3a8-48d0-b29e-3658cb63bdf5",
		block_type: {
			id: "52d6b05e-a3a8-48d0-b29e-3658cb63bdf5",
			created: "2024-12-02T18:19:08.045419Z",
			updated: "2024-12-02T18:19:08.045420Z",
			name: "AWS Secret",
			slug: "aws-secret",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-aws/secrets_manager/#prefect_aws.secrets_manager.AwsSecret",
			description:
				"Manages a secret in AWS's Secrets Manager. This block is part of the prefect-aws collection. Install prefect-aws with `pip install prefect-aws` to use this block.",
			code_example:
				'```python\nfrom prefect_aws.secrets_manager import AwsSecret\n\naws_secret_block = AwsSecret.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.14",
	},
	{
		id: "801b5c4e-94fb-4805-a0e8-a75cc5fb6e40",
		created: "2024-12-02T18:19:08.075401Z",
		updated: "2024-12-02T18:19:08.075402Z",
		checksum:
			"sha256:17b73297ed60f080fb235b3a5a145a6d9b28a09b3ff2d9d17810b5e2c2075ebe",
		fields: {
			title: "AwsCredentials",
			description:
				"Block used to manage authentication with AWS. AWS authentication is\nhandled via the `boto3` module. Refer to the\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)\nfor more info about the possible credential configurations.",
			type: "object",
			properties: {
				aws_access_key_id: {
					title: "AWS Access Key ID",
					description: "A specific AWS access key ID.",
					type: "string",
				},
				aws_secret_access_key: {
					title: "AWS Access Key Secret",
					description: "A specific AWS secret access key.",
					type: "string",
					writeOnly: true,
					format: "password",
				},
				aws_session_token: {
					title: "AWS Session Token",
					description:
						"The session key for your AWS account. This is only needed when you are using temporary credentials.",
					type: "string",
				},
				profile_name: {
					title: "Profile Name",
					description: "The profile to use when creating your session.",
					type: "string",
				},
				region_name: {
					title: "Region Name",
					description:
						"The AWS Region where you want to create new connections.",
					type: "string",
				},
				aws_client_parameters: {
					title: "AWS Client Parameters",
					description: "Extra parameters to initialize the Client.",
					allOf: [
						{
							$ref: "#/definitions/AwsClientParameters",
						},
					],
				},
			},
			block_type_slug: "aws-credentials",
			secret_fields: ["aws_secret_access_key"],
			definitions: {
				AwsClientParameters: {
					title: "AwsClientParameters",
					description:
						'Model used to manage extra parameters that you can pass when you initialize\nthe Client. If you want to find more information, see\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html)\nfor more info about the possible client configurations.\n\nAttributes:\n    api_version: The API version to use. By default, botocore will\n        use the latest API version when creating a client. You only need\n        to specify this parameter if you want to use a previous API version\n        of the client.\n    use_ssl: Whether or not to use SSL. By default, SSL is used.\n        Note that not all services support non-ssl connections.\n    verify: Whether or not to verify SSL certificates. By default\n        SSL certificates are verified. If False, SSL will still be used\n        (unless use_ssl is False), but SSL certificates\n        will not be verified. Passing a file path to this is deprecated.\n    verify_cert_path: A filename of the CA cert bundle to\n        use. You can specify this argument if you want to use a\n        different CA cert bundle than the one used by botocore.\n    endpoint_url: The complete URL to use for the constructed\n        client. Normally, botocore will automatically construct the\n        appropriate URL to use when communicating with a service. You\n        can specify a complete URL (including the "http/https" scheme)\n        to override this behavior. If this value is provided,\n        then ``use_ssl`` is ignored.\n    config: Advanced configuration for Botocore clients. See\n        [botocore docs](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)\n        for more details.',
					type: "object",
					properties: {
						api_version: {
							title: "API Version",
							description: "The API version to use.",
							type: "string",
						},
						use_ssl: {
							title: "Use SSL",
							description: "Whether or not to use SSL.",
							default: true,
							type: "boolean",
						},
						verify: {
							title: "Verify",
							description: "Whether or not to verify SSL certificates.",
							default: true,
							anyOf: [
								{
									type: "boolean",
								},
								{
									type: "string",
									format: "file-path",
								},
							],
						},
						verify_cert_path: {
							title: "Certificate Authority Bundle File Path",
							description: "Path to the CA cert bundle to use.",
							format: "file-path",
							type: "string",
						},
						endpoint_url: {
							title: "Endpoint URL",
							description:
								"The complete URL to use for the constructed client.",
							type: "string",
						},
						config: {
							title: "Botocore Config",
							description: "Advanced configuration for Botocore clients.",
							type: "object",
						},
					},
				},
			},
			block_schema_references: {},
		},
		block_type_id: "4e6bf197-73c5-4101-b5eb-789d4f47010f",
		block_type: {
			id: "4e6bf197-73c5-4101-b5eb-789d4f47010f",
			created: "2024-12-02T18:19:08.044621Z",
			updated: "2024-12-02T18:19:08.044624Z",
			name: "AWS Credentials",
			slug: "aws-credentials",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png",
			documentation_url:
				"https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.AwsCredentials",
			description:
				"Block used to manage authentication with AWS. AWS authentication is\nhandled via the `boto3` module. Refer to the\n[boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)\nfor more info about the possible credential configurations. This block is part of the prefect-aws collection. Install prefect-aws with `pip install prefect-aws` to use this block.",
			code_example:
				'Load stored AWS credentials:\n```python\nfrom prefect_aws import AwsCredentials\n\naws_credentials_block = AwsCredentials.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "0.4.14",
	},
	{
		id: "ca268dbd-b929-4d2f-890d-1c646b4dc59c",
		created: "2024-12-02T18:19:08.040275Z",
		updated: "2024-12-02T18:19:08.040277Z",
		checksum:
			"sha256:43bb8145a5f701e6453ca0f91ccd5640f291960b02d916055ff1523bab896f33",
		fields: {
			block_type_slug: "smb",
			description: "Store data as a file on a SMB share.",
			properties: {
				share_path: {
					description: "SMB target (requires <SHARE>, followed by <PATH>).",
					examples: ["/SHARE/dir/subdir"],
					title: "Share Path",
					type: "string",
				},
				smb_username: {
					anyOf: [
						{
							format: "password",
							type: "string",
							writeOnly: true,
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Username with access to the target SMB SHARE.",
					title: "SMB Username",
				},
				smb_password: {
					anyOf: [
						{
							format: "password",
							type: "string",
							writeOnly: true,
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Password for SMB access.",
					title: "SMB Password",
				},
				smb_host: {
					description: "SMB server/hostname.",
					title: "SMB server/hostname",
					type: "string",
				},
				smb_port: {
					anyOf: [
						{
							type: "integer",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "SMB port (default: 445).",
					title: "SMB port",
				},
			},
			required: ["share_path", "smb_host"],
			secret_fields: ["smb_username", "smb_password"],
			title: "SMB",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "a7a14340-b14f-48bc-b45e-315a36e525da",
		block_type: {
			id: "a7a14340-b14f-48bc-b45e-315a36e525da",
			created: "2024-12-02T18:19:08.037544Z",
			updated: "2024-12-02T18:19:08.037546Z",
			name: "SMB",
			slug: "smb",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/3f624663f7beb97d011d011bffd51ecf6c499efc-195x195.png",
			documentation_url:
				"https://docs.prefect.io/latest/develop/results#specifying-a-default-filesystem",
			description: "Store data as a file on a SMB share.",
			code_example:
				'Load stored SMB config:\n\n```python\nfrom prefect.filesystems import SMB\nsmb_block = SMB.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["write-path", "read-path", "put-directory", "get-directory"],
		version: "3.1.5",
	},
	{
		id: "89829196-90dd-4e5a-8c9c-f070a993fea3",
		created: "2024-12-02T18:19:08.034388Z",
		updated: "2024-12-02T18:19:08.034391Z",
		checksum:
			"sha256:efb6b7304d9cadaf09a18abc60be7ae86aec60dbd7dba345faa7ba1e960b211f",
		fields: {
			block_type_slug: "remote-file-system",
			description:
				'Store data as a file on a remote file system.\n\nSupports any remote file system supported by `fsspec`. The file system is specified\nusing a protocol. For example, "s3://my-bucket/my-folder/" will use S3.',
			properties: {
				basepath: {
					description: "Default path for this block to write to.",
					examples: ["s3://my-bucket/my-folder/"],
					title: "Basepath",
					type: "string",
				},
				settings: {
					description: "Additional settings to pass through to fsspec.",
					title: "Settings",
					type: "object",
				},
			},
			required: ["basepath"],
			secret_fields: [],
			title: "RemoteFileSystem",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "8aa06c7d-6087-4d0b-9c33-7e1d99755931",
		block_type: {
			id: "8aa06c7d-6087-4d0b-9c33-7e1d99755931",
			created: "2024-12-02T18:19:08.031897Z",
			updated: "2024-12-02T18:19:08.031900Z",
			name: "Remote File System",
			slug: "remote-file-system",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/e86b41bc0f9c99ba9489abeee83433b43d5c9365-48x48.png",
			documentation_url:
				"https://docs.prefect.io/latest/develop/results#specifying-a-default-filesystem",
			description:
				'Store data as a file on a remote file system.\n\nSupports any remote file system supported by `fsspec`. The file system is specified\nusing a protocol. For example, "s3://my-bucket/my-folder/" will use S3.',
			code_example:
				'Load stored remote file system config:\n```python\nfrom prefect.filesystems import RemoteFileSystem\n\nremote_file_system_block = RemoteFileSystem.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: ["write-path", "read-path", "put-directory", "get-directory"],
		version: "3.1.5",
	},
	{
		id: "f108f04d-7c4d-44a7-b3f9-9c87787d1442",
		created: "2024-12-02T18:19:08.010683Z",
		updated: "2024-12-02T18:19:08.010685Z",
		checksum:
			"sha256:d1323de7a11a0fcd1854515cf86358ad819f51e8d43f5ba176578965f54b2f9f",
		fields: {
			block_type_slug: "string",
			description:
				"A block that represents a string. Deprecated, please use Variables to store string data instead.",
			properties: {
				value: {
					description: "A string value.",
					title: "Value",
					type: "string",
				},
			},
			required: ["value"],
			secret_fields: [],
			title: "String",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "2e3caedc-b2fd-43ce-9c50-34a1f4a927c9",
		block_type: {
			id: "2e3caedc-b2fd-43ce-9c50-34a1f4a927c9",
			created: "2024-12-02T18:19:08.008290Z",
			updated: "2024-12-02T18:19:08.008292Z",
			name: "String",
			slug: "string",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/c262ea2c80a2c043564e8763f3370c3db5a6b3e6-48x48.png",
			documentation_url: "https://docs.prefect.io/latest/develop/blocks",
			description:
				"A block that represents a string. Deprecated, please use Variables to store string data instead.",
			code_example:
				'Load a stored string value:\n```python\nfrom prefect.blocks.system import String\n\nstring_block = String.load("BLOCK_NAME")\n```',
			is_protected: false,
		},
		capabilities: [],
		version: "3.1.5",
	},
	{
		id: "70e721ac-147b-4cf0-bb30-fe3de771acd4",
		created: "2024-12-02T18:19:07.999691Z",
		updated: "2024-12-02T18:19:07.999694Z",
		checksum:
			"sha256:ca1ce43172228b65a570b1a5de9cdbd9813945e672807dc42d21b69d9d3977e7",
		fields: {
			block_type_slug: "sendgrid-email",
			description: "Enables sending notifications via Sendgrid email service.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				api_key: {
					description: "The API Key associated with your sendgrid account.",
					format: "password",
					title: "API Key",
					type: "string",
					writeOnly: true,
				},
				sender_email: {
					description: "The sender email id.",
					examples: ["test-support@gmail.com"],
					title: "Sender email id",
					type: "string",
				},
				to_emails: {
					description: "Email ids of all recipients.",
					examples: ['"recipient1@gmail.com"'],
					items: {
						type: "string",
					},
					title: "Recipient emails",
					type: "array",
				},
			},
			required: ["api_key", "sender_email", "to_emails"],
			secret_fields: ["api_key"],
			title: "SendgridEmail",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "3c3a7fc3-30fe-481c-a821-471153ebed32",
		block_type: {
			id: "3c3a7fc3-30fe-481c-a821-471153ebed32",
			created: "2024-12-02T18:19:07.997138Z",
			updated: "2024-12-02T18:19:07.997140Z",
			name: "Sendgrid Email",
			slug: "sendgrid-email",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/82bc6ed16ca42a2252a5512c72233a253b8a58eb-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description: "Enables sending notifications via Sendgrid email service.",
			code_example:
				'Load a saved Sendgrid and send a email message:\n```python\nfrom prefect.blocks.notifications import SendgridEmail\n\nsendgrid_block = SendgridEmail.load("BLOCK_NAME")\n\nsendgrid_block.notify("Hello from Prefect!")',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "444b3432-d9a1-4033-b665-9fa137873b2c",
		created: "2024-12-02T18:19:07.993729Z",
		updated: "2024-12-02T18:19:07.993731Z",
		checksum:
			"sha256:f6c8015bc4daad1c21186e552098da5a5a72c0410ee68a0ac0c0e5b56004433f",
		fields: {
			block_type_slug: "custom-webhook",
			description:
				"Enables sending notifications via any custom webhook.\n\nAll nested string param contains `{{key}}` will be substituted with value from context/secrets.\n\nContext values include: `subject`, `body` and `name`.",
			properties: {
				name: {
					description: "Name of the webhook.",
					title: "Name",
					type: "string",
				},
				url: {
					description: "The webhook URL.",
					examples: ["https://hooks.slack.com/XXX"],
					title: "Webhook URL",
					type: "string",
				},
				method: {
					default: "POST",
					description: "The webhook request method. Defaults to `POST`.",
					enum: ["GET", "POST", "PUT", "PATCH", "DELETE"],
					title: "Method",
					type: "string",
				},
				params: {
					anyOf: [
						{
							additionalProperties: {
								type: "string",
							},
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Custom query params.",
					title: "Query Params",
				},
				json_data: {
					anyOf: [
						{
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Send json data as payload.",
					examples: [
						'{"text": "{{subject}}\\n{{body}}", "title": "{{name}}", "token": "{{tokenFromSecrets}}"}',
					],
					title: "JSON Data",
				},
				form_data: {
					anyOf: [
						{
							additionalProperties: {
								type: "string",
							},
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description:
						"Send form data as payload. Should not be used together with _JSON Data_.",
					examples: [
						'{"text": "{{subject}}\\n{{body}}", "title": "{{name}}", "token": "{{tokenFromSecrets}}"}',
					],
					title: "Form Data",
				},
				headers: {
					anyOf: [
						{
							additionalProperties: {
								type: "string",
							},
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Custom headers.",
					title: "Headers",
				},
				cookies: {
					anyOf: [
						{
							additionalProperties: {
								type: "string",
							},
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Custom cookies.",
					title: "Cookies",
				},
				timeout: {
					default: 10,
					description: "Request timeout in seconds. Defaults to 10.",
					title: "Timeout",
					type: "number",
				},
				secrets: {
					description:
						"A dictionary of secret values to be substituted in other configs.",
					examples: ['{"tokenFromSecrets":"SomeSecretToken"}'],
					title: "Custom Secret Values",
					type: "object",
				},
			},
			required: ["name", "url"],
			secret_fields: ["secrets.*"],
			title: "CustomWebhookNotificationBlock",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "cf9fff3d-ec21-4438-872a-5b70de9c6e2e",
		block_type: {
			id: "cf9fff3d-ec21-4438-872a-5b70de9c6e2e",
			created: "2024-12-02T18:19:07.990583Z",
			updated: "2024-12-02T18:19:07.990585Z",
			name: "Custom Webhook",
			slug: "custom-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/c7247cb359eb6cf276734d4b1fbf00fb8930e89e-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via any custom webhook.\n\nAll nested string param contains `{{key}}` will be substituted with value from context/secrets.\n\nContext values include: `subject`, `body` and `name`.",
			code_example:
				'Load a saved custom webhook and send a message:\n```python\nfrom prefect.blocks.notifications import CustomWebhookNotificationBlock\n\ncustom_webhook_block = CustomWebhookNotificationBlock.load("BLOCK_NAME")\n\ncustom_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "e04c6053-f63e-41a1-8329-dc54f1e66039",
		created: "2024-12-02T18:19:07.987142Z",
		updated: "2024-12-02T18:19:07.987144Z",
		checksum:
			"sha256:6a52b1831a9e289e74a3dc03986ca1b00aaf8c4c523fd9dcacd1982e45bfe956",
		fields: {
			block_type_slug: "discord-webhook",
			description:
				"Enables sending notifications via a provided Discord webhook.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				webhook_id: {
					description:
						"The first part of 2 tokens provided to you after creating a incoming-webhook.",
					format: "password",
					title: "Webhook Id",
					type: "string",
					writeOnly: true,
				},
				webhook_token: {
					description:
						"The second part of 2 tokens provided to you after creating a incoming-webhook.",
					format: "password",
					title: "Webhook Token",
					type: "string",
					writeOnly: true,
				},
				botname: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description:
						"Identify the name of the bot that should issue the message. If one isn't specified then the default is to just use your account (associated with the incoming-webhook).",
					title: "Bot name",
				},
				tts: {
					default: false,
					description: "Whether to enable Text-To-Speech.",
					title: "Tts",
					type: "boolean",
				},
				include_image: {
					default: false,
					description:
						"Whether to include an image in-line with the message describing the notification type.",
					title: "Include Image",
					type: "boolean",
				},
				avatar: {
					default: false,
					description: "Whether to override the default discord avatar icon.",
					title: "Avatar",
					type: "boolean",
				},
				avatar_url: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: false,
					description:
						"Over-ride the default discord avatar icon URL. By default this is not set and Apprise chooses the URL dynamically based on the type of message (info, success, warning, or error).",
					title: "Avatar URL",
				},
			},
			required: ["webhook_id", "webhook_token"],
			secret_fields: ["webhook_id", "webhook_token"],
			title: "DiscordWebhook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "214639df-0e7d-4dba-96ef-b7d29aaa838e",
		block_type: {
			id: "214639df-0e7d-4dba-96ef-b7d29aaa838e",
			created: "2024-12-02T18:19:07.984192Z",
			updated: "2024-12-02T18:19:07.984195Z",
			name: "Discord Webhook",
			slug: "discord-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/9e94976c80ef925b66d24e5d14f0d47baa6b8f88-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via a provided Discord webhook.",
			code_example:
				'Load a saved Discord webhook and send a message:\n```python\nfrom prefect.blocks.notifications import DiscordWebhook\n\ndiscord_webhook_block = DiscordWebhook.load("BLOCK_NAME")\n\ndiscord_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "64065cff-1b99-4259-9f26-e74cb671009d",
		created: "2024-12-02T18:19:07.980880Z",
		updated: "2024-12-02T18:19:07.980882Z",
		checksum:
			"sha256:01f4ee2616acf43a554c44388e36439ebe3ad0f8e58e67279a0116d476dd5e61",
		fields: {
			block_type_slug: "mattermost-webhook",
			description:
				"Enables sending notifications via a provided Mattermost webhook.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				hostname: {
					description: "The hostname of your Mattermost server.",
					examples: ["Mattermost.example.com"],
					title: "Hostname",
					type: "string",
				},
				token: {
					description: "The token associated with your Mattermost webhook.",
					format: "password",
					title: "Token",
					type: "string",
					writeOnly: true,
				},
				botname: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The name of the bot that will send the message.",
					title: "Bot name",
				},
				channels: {
					anyOf: [
						{
							items: {
								type: "string",
							},
							type: "array",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The channel(s) you wish to notify.",
					title: "Channels",
				},
				include_image: {
					default: false,
					description:
						"Whether to include the Apprise status image in the message.",
					title: "Include Image",
					type: "boolean",
				},
				path: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description:
						"An optional sub-path specification to append to the hostname.",
					title: "Path",
				},
				port: {
					default: 8065,
					description: "The port of your Mattermost server.",
					title: "Port",
					type: "integer",
				},
			},
			required: ["hostname", "token"],
			secret_fields: ["token"],
			title: "MattermostWebhook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "37383b6e-e219-4a38-b4cb-a98195d75534",
		block_type: {
			id: "37383b6e-e219-4a38-b4cb-a98195d75534",
			created: "2024-12-02T18:19:07.977922Z",
			updated: "2024-12-02T18:19:07.977924Z",
			name: "Mattermost Webhook",
			slug: "mattermost-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/1350a147130bf82cbc799a5f868d2c0116207736-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via a provided Mattermost webhook.",
			code_example:
				'Load a saved Mattermost webhook and send a message:\n```python\nfrom prefect.blocks.notifications import MattermostWebhook\n\nmattermost_webhook_block = MattermostWebhook.load("BLOCK_NAME")\n\nmattermost_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "67aa7c10-50db-4fce-a9eb-68bbde21ef3d",
		created: "2024-12-02T18:19:07.974645Z",
		updated: "2024-12-02T18:19:07.974648Z",
		checksum:
			"sha256:748fdf50db8e686cd50865d2079273095912697aefd180b690c8dbfd80f0b362",
		fields: {
			block_type_slug: "opsgenie-webhook",
			description:
				"Enables sending notifications via a provided Opsgenie webhook.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				apikey: {
					description: "The API Key associated with your Opsgenie account.",
					format: "password",
					title: "API Key",
					type: "string",
					writeOnly: true,
				},
				target_user: {
					anyOf: [
						{
							items: {},
							type: "array",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The user(s) you wish to notify.",
					title: "Target User",
				},
				target_team: {
					anyOf: [
						{
							items: {},
							type: "array",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The team(s) you wish to notify.",
					title: "Target Team",
				},
				target_schedule: {
					anyOf: [
						{
							items: {},
							type: "array",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The schedule(s) you wish to notify.",
					title: "Target Schedule",
				},
				target_escalation: {
					anyOf: [
						{
							items: {},
							type: "array",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The escalation(s) you wish to notify.",
					title: "Target Escalation",
				},
				region_name: {
					default: "us",
					description: "The 2-character region code.",
					enum: ["us", "eu"],
					title: "Region Name",
					type: "string",
				},
				batch: {
					default: false,
					description:
						"Notify all targets in batches (instead of individually).",
					title: "Batch",
					type: "boolean",
				},
				tags: {
					anyOf: [
						{
							items: {},
							type: "array",
						},
						{
							type: "null",
						},
					],
					default: null,
					description:
						"A comma-separated list of tags you can associate with your Opsgenie message.",
					examples: ['["tag1", "tag2"]'],
					title: "Tags",
				},
				priority: {
					anyOf: [
						{
							type: "integer",
						},
						{
							type: "null",
						},
					],
					default: 3,
					description:
						"The priority to associate with the message. It is on a scale between 1 (LOW) and 5 (EMERGENCY).",
					title: "Priority",
				},
				alias: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The alias to associate with the message.",
					title: "Alias",
				},
				entity: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The entity to associate with the message.",
					title: "Entity",
				},
				details: {
					anyOf: [
						{
							additionalProperties: {
								type: "string",
							},
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Additional details composed of key/values pairs.",
					examples: ['{"key1": "value1", "key2": "value2"}'],
					title: "Details",
				},
			},
			required: ["apikey"],
			secret_fields: ["apikey"],
			title: "OpsgenieWebhook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "9eee09ba-8a95-4495-a94d-536b0030ae26",
		block_type: {
			id: "9eee09ba-8a95-4495-a94d-536b0030ae26",
			created: "2024-12-02T18:19:07.971144Z",
			updated: "2024-12-02T18:19:07.971146Z",
			name: "Opsgenie Webhook",
			slug: "opsgenie-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/d8b5bc6244ae6cd83b62ec42f10d96e14d6e9113-280x280.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via a provided Opsgenie webhook.",
			code_example:
				'Load a saved Opsgenie webhook and send a message:\n```python\nfrom prefect.blocks.notifications import OpsgenieWebhook\nopsgenie_webhook_block = OpsgenieWebhook.load("BLOCK_NAME")\nopsgenie_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "cb69149f-0aea-40ee-8cce-d1f200f394c0",
		created: "2024-12-02T18:19:07.967883Z",
		updated: "2024-12-02T18:19:07.967886Z",
		checksum:
			"sha256:a3c827e6f0554918bbd7a4161795ad86a5e5baf980993cdc6e9e0d58c08b9aec",
		fields: {
			block_type_slug: "twilio-sms",
			description: "Enables sending notifications via Twilio SMS.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				account_sid: {
					description:
						"The Twilio Account SID - it can be found on the homepage of the Twilio console.",
					title: "Account Sid",
					type: "string",
				},
				auth_token: {
					description:
						"The Twilio Authentication Token - it can be found on the homepage of the Twilio console.",
					format: "password",
					title: "Auth Token",
					type: "string",
					writeOnly: true,
				},
				from_phone_number: {
					description:
						"The valid Twilio phone number to send the message from.",
					examples: ["18001234567"],
					title: "From Phone Number",
					type: "string",
				},
				to_phone_numbers: {
					description:
						"A list of valid Twilio phone number(s) to send the message to.",
					examples: ["18004242424"],
					items: {
						type: "string",
					},
					title: "To Phone Numbers",
					type: "array",
				},
			},
			required: [
				"account_sid",
				"auth_token",
				"from_phone_number",
				"to_phone_numbers",
			],
			secret_fields: ["auth_token"],
			title: "TwilioSMS",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "5a23a05f-7ce6-4aef-8acf-3184a6ce5808",
		block_type: {
			id: "5a23a05f-7ce6-4aef-8acf-3184a6ce5808",
			created: "2024-12-02T18:19:07.964913Z",
			updated: "2024-12-02T18:19:07.964915Z",
			name: "Twilio SMS",
			slug: "twilio-sms",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/8bd8777999f82112c09b9c8d57083ac75a4a0d65-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description: "Enables sending notifications via Twilio SMS.",
			code_example:
				'Load a saved `TwilioSMS` block and send a message:\n```python\nfrom prefect.blocks.notifications import TwilioSMS\ntwilio_webhook_block = TwilioSMS.load("BLOCK_NAME")\ntwilio_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "64bb5db2-92e3-440b-9225-e2e9a44709d6",
		created: "2024-12-02T18:19:07.961436Z",
		updated: "2024-12-02T18:19:07.961439Z",
		checksum:
			"sha256:133ccf80404b874c09cc28c5fca18afb8e6e5409fff1b2615775f5f9b73c878e",
		fields: {
			block_type_slug: "pager-duty-webhook",
			description:
				"Enables sending notifications via a provided PagerDuty webhook.",
			properties: {
				notify_type: {
					default: "info",
					description: "The severity of the notification.",
					enum: ["info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				integration_key: {
					description:
						"This can be found on the Events API V2 integration's detail page, and is also referred to as a Routing Key. This must be provided alongside `api_key`, but will error if provided alongside `url`.",
					format: "password",
					title: "Integration Key",
					type: "string",
					writeOnly: true,
				},
				api_key: {
					description:
						"This can be found under Integrations. This must be provided alongside `integration_key`, but will error if provided alongside `url`.",
					format: "password",
					title: "API Key",
					type: "string",
					writeOnly: true,
				},
				source: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: "Prefect",
					description: "The source string as part of the payload.",
					title: "Source",
				},
				component: {
					default: "Notification",
					description: "The component string as part of the payload.",
					title: "Component",
					type: "string",
				},
				group: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The group string as part of the payload.",
					title: "Group",
				},
				class_id: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "The class string as part of the payload.",
					title: "Class ID",
				},
				region_name: {
					default: "us",
					description: "The region name.",
					enum: ["us", "eu"],
					title: "Region Name",
					type: "string",
				},
				clickable_url: {
					anyOf: [
						{
							format: "uri",
							minLength: 1,
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "A clickable URL to associate with the notice.",
					title: "Clickable URL",
				},
				include_image: {
					default: true,
					description:
						"Associate the notification status via a represented icon.",
					title: "Include Image",
					type: "boolean",
				},
				custom_details: {
					anyOf: [
						{
							additionalProperties: {
								type: "string",
							},
							type: "object",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Additional details to include as part of the payload.",
					examples: ['{"disk_space_left": "145GB"}'],
					title: "Custom Details",
				},
			},
			required: ["integration_key", "api_key"],
			secret_fields: ["integration_key", "api_key"],
			title: "PagerDutyWebHook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "1be1f6e1-496c-4962-9914-2da54d9e3a7d",
		block_type: {
			id: "1be1f6e1-496c-4962-9914-2da54d9e3a7d",
			created: "2024-12-02T18:19:07.957340Z",
			updated: "2024-12-02T18:19:07.957342Z",
			name: "Pager Duty Webhook",
			slug: "pager-duty-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/8dbf37d17089c1ce531708eac2e510801f7b3aee-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via a provided PagerDuty webhook.",
			code_example:
				'Load a saved PagerDuty webhook and send a message:\n```python\nfrom prefect.blocks.notifications import PagerDutyWebHook\npagerduty_webhook_block = PagerDutyWebHook.load("BLOCK_NAME")\npagerduty_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "43ecde89-9174-4dd2-9da0-085946f622ed",
		created: "2024-12-02T18:19:07.953990Z",
		updated: "2024-12-02T18:19:07.953993Z",
		checksum:
			"sha256:d3ad686c4c75d7f4c4db5075e18170ce22a1f25f98f04c7cc8e2cc12656e9c2f",
		fields: {
			block_type_slug: "ms-teams-webhook",
			description:
				"Enables sending notifications via a provided Microsoft Teams webhook.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				url: {
					description:
						"The Microsoft Power Automate (Workflows) URL used to send notifications to Teams.",
					examples: [
						"https://prod-NO.LOCATION.logic.azure.com:443/workflows/WFID/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=SIGNATURE",
					],
					format: "password",
					title: "Webhook URL",
					type: "string",
					writeOnly: true,
				},
				allow_private_urls: {
					default: true,
					description:
						"Whether to allow notifications to private URLs. Defaults to True.",
					title: "Allow Private Urls",
					type: "boolean",
				},
				include_image: {
					default: true,
					description: "Include an image with the notification.",
					title: "Include Image",
					type: "boolean",
				},
				wrap: {
					default: true,
					description: "Wrap the notification text.",
					title: "Wrap",
					type: "boolean",
				},
			},
			required: ["url"],
			secret_fields: ["url"],
			title: "MicrosoftTeamsWebhook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "0b1af0c4-aa8b-469d-8aff-fecb547225ad",
		block_type: {
			id: "0b1af0c4-aa8b-469d-8aff-fecb547225ad",
			created: "2024-12-02T18:19:07.951227Z",
			updated: "2024-12-02T18:19:07.951229Z",
			name: "Microsoft Teams Webhook",
			slug: "ms-teams-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/817efe008a57f0a24f3587414714b563e5e23658-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via a provided Microsoft Teams webhook.",
			code_example:
				'Load a saved Teams webhook and send a message:\n```python\nfrom prefect.blocks.notifications import MicrosoftTeamsWebhook\nteams_webhook_block = MicrosoftTeamsWebhook.load("BLOCK_NAME")\nteams_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "21d5c052-7335-44a9-9480-adb85c127a3d",
		created: "2024-12-02T18:19:07.947731Z",
		updated: "2024-12-02T18:19:07.947734Z",
		checksum:
			"sha256:27d4fa59cceca2b98793d6ef0f97fd3b416f9cacd26912573d8edc05ca1666b4",
		fields: {
			block_type_slug: "slack-webhook",
			description:
				"Enables sending notifications via a provided Slack webhook.",
			properties: {
				notify_type: {
					default: "prefect_default",
					description:
						"The type of notification being performed; the prefect_default is a plain notification that does not attach an image.",
					enum: ["prefect_default", "info", "success", "warning", "failure"],
					title: "Notify Type",
					type: "string",
				},
				url: {
					description: "Slack incoming webhook URL used to send notifications.",
					examples: ["https://hooks.slack.com/XXX"],
					format: "password",
					title: "Webhook URL",
					type: "string",
					writeOnly: true,
				},
				allow_private_urls: {
					default: true,
					description:
						"Whether to allow notifications to private URLs. Defaults to True.",
					title: "Allow Private Urls",
					type: "boolean",
				},
			},
			required: ["url"],
			secret_fields: ["url"],
			title: "SlackWebhook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "ecf55c95-35f8-47f4-b8b5-2e9793486fee",
		block_type: {
			id: "ecf55c95-35f8-47f4-b8b5-2e9793486fee",
			created: "2024-12-02T18:19:07.944913Z",
			updated: "2024-12-02T18:19:07.944915Z",
			name: "Slack Webhook",
			slug: "slack-webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/c1965ecbf8704ee1ea20d77786de9a41ce1087d1-500x500.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
			description:
				"Enables sending notifications via a provided Slack webhook.",
			code_example:
				'Load a saved Slack webhook and send a message:\n```python\nfrom prefect.blocks.notifications import SlackWebhook\n\nslack_webhook_block = SlackWebhook.load("BLOCK_NAME")\nslack_webhook_block.notify("Hello from Prefect!")\n```',
			is_protected: false,
		},
		capabilities: ["notify"],
		version: "3.1.5",
	},
	{
		id: "661c5b40-14da-437e-a1b2-9f66ecc9e3bc",
		created: "2024-12-02T18:19:07.941270Z",
		updated: "2024-12-02T18:19:07.941272Z",
		checksum:
			"sha256:80dd31d7cc72fba9f3005c9692797050a118b5b24f3354df05ec1b7de9f0abbd",
		fields: {
			block_type_slug: "local-file-system",
			description: "Store data as a file on a local file system.",
			properties: {
				basepath: {
					anyOf: [
						{
							type: "string",
						},
						{
							type: "null",
						},
					],
					default: null,
					description: "Default local path for this block to write to.",
					title: "Basepath",
				},
			},
			secret_fields: [],
			title: "LocalFileSystem",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "6dd4e5d7-089c-49e7-8035-2b7143ab46c4",
		block_type: {
			id: "6dd4e5d7-089c-49e7-8035-2b7143ab46c4",
			created: "2024-12-02T18:19:07.939212Z",
			updated: "2024-12-02T18:19:08.027000Z",
			name: "Local File System",
			slug: "local-file-system",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/ad39089fa66d273b943394a68f003f7a19aa850e-48x48.png",
			documentation_url:
				"https://docs.prefect.io/latest/develop/results#specifying-a-default-filesystem",
			description: "Store data as a file on a local file system.",
			code_example:
				'Load stored local file system config:\n```python\nfrom prefect.filesystems import LocalFileSystem\n\nlocal_file_system_block = LocalFileSystem.load("BLOCK_NAME")\n```',
			is_protected: true,
		},
		capabilities: ["write-path", "read-path", "put-directory", "get-directory"],
		version: "3.1.5",
	},
	{
		id: "1eda532a-2ec2-40a9-9d95-c29ad28ad0e4",
		created: "2024-12-02T18:19:07.935829Z",
		updated: "2024-12-02T18:19:07.935832Z",
		checksum:
			"sha256:fab1c36f1340a9fee1a4de830018147ac5266bf9121de8df9c1c23d8897cd701",
		fields: {
			block_type_slug: "secret",
			description:
				"A block that represents a secret value. The value stored in this block will be obfuscated when\nthis block is viewed or edited in the UI.",
			properties: {
				value: {
					anyOf: [
						{
							format: "password",
							type: "string",
							writeOnly: true,
						},
						{
							title: "string",
							type: "string",
						},
						{
							$ref: "#/definitions/JsonValue",
							title: "JSON",
						},
					],
					description: "A value that should be kept secret.",
					examples: [
						"sk-1234567890",
						{
							password: "s3cr3t",
							username: "johndoe",
						},
					],
					format: "password",
					title: "Value",
					writeOnly: true,
				},
			},
			required: ["value"],
			secret_fields: ["value"],
			title: "Secret",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "b39155f0-d9ad-4c07-adda-8ba323701a3b",
		block_type: {
			id: "b39155f0-d9ad-4c07-adda-8ba323701a3b",
			created: "2024-12-02T18:19:07.933740Z",
			updated: "2024-12-02T18:19:08.018000Z",
			name: "Secret",
			slug: "secret",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/c6f20e556dd16effda9df16551feecfb5822092b-48x48.png",
			documentation_url: "https://docs.prefect.io/latest/develop/blocks",
			description:
				"A block that represents a secret value. The value stored in this block will be obfuscated when\nthis block is viewed or edited in the UI.",
			code_example:
				'```python\nfrom prefect.blocks.system import Secret\n\nSecret(value="sk-1234567890").save("BLOCK_NAME", overwrite=True)\n\nsecret_block = Secret.load("BLOCK_NAME")\n\n# Access the stored secret\nsecret_block.get()\n```',
			is_protected: true,
		},
		capabilities: [],
		version: "3.1.5",
	},
	{
		id: "33293b17-4665-431f-aef4-cb975af614b2",
		created: "2024-12-02T18:19:07.930369Z",
		updated: "2024-12-02T18:19:07.930372Z",
		checksum:
			"sha256:94cacaae861dc63b4fcfef96972d9269bb7cb8897a0591a6fd2ac6d0ee64571f",
		fields: {
			block_type_slug: "date-time",
			description:
				"A block that represents a datetime. Deprecated, please use Variables to store datetime data instead.",
			properties: {
				value: {
					description: "An ISO 8601-compatible datetime value.",
					format: "date-time",
					title: "Value",
					type: "string",
				},
			},
			required: ["value"],
			secret_fields: [],
			title: "DateTime",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "0bd8b72c-ed7e-4151-8c36-ec746b96d61c",
		block_type: {
			id: "0bd8b72c-ed7e-4151-8c36-ec746b96d61c",
			created: "2024-12-02T18:19:07.928350Z",
			updated: "2024-12-02T18:19:08.014000Z",
			name: "Date Time",
			slug: "date-time",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/8b3da9a6621e92108b8e6a75b82e15374e170ff7-48x48.png",
			documentation_url: "https://docs.prefect.io/latest/develop/blocks",
			description:
				"A block that represents a datetime. Deprecated, please use Variables to store datetime data instead.",
			code_example:
				'Load a stored JSON value:\n```python\nfrom prefect.blocks.system import DateTime\n\ndata_time_block = DateTime.load("BLOCK_NAME")\n```',
			is_protected: true,
		},
		capabilities: [],
		version: "3.1.5",
	},
	{
		id: "2d05d6bb-bc60-4351-b53a-bdf2e3507392",
		created: "2024-12-02T18:19:07.924907Z",
		updated: "2024-12-02T18:19:07.924910Z",
		checksum:
			"sha256:0f01d400eb1ebd964d491132cda72e6a6d843f8ce940397b3dba7be219852106",
		fields: {
			block_type_slug: "json",
			description:
				"A block that represents JSON. Deprecated, please use Variables to store JSON data instead.",
			properties: {
				value: {
					description: "A JSON-compatible value.",
					title: "Value",
				},
			},
			required: ["value"],
			secret_fields: [],
			title: "JSON",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "a0d50399-39b7-44ea-a0b8-4c5e99388b8f",
		block_type: {
			id: "a0d50399-39b7-44ea-a0b8-4c5e99388b8f",
			created: "2024-12-02T18:19:07.922307Z",
			updated: "2024-12-02T18:19:08.003000Z",
			name: "JSON",
			slug: "json",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/4fcef2294b6eeb423b1332d1ece5156bf296ff96-48x48.png",
			documentation_url: "https://docs.prefect.io/latest/develop/blocks",
			description:
				"A block that represents JSON. Deprecated, please use Variables to store JSON data instead.",
			code_example:
				'Load a stored JSON value:\n```python\nfrom prefect.blocks.system import JSON\n\njson_block = JSON.load("BLOCK_NAME")\n```',
			is_protected: true,
		},
		capabilities: [],
		version: "3.1.5",
	},
	{
		id: "8518c616-f28f-48ac-866a-b0cbf7a86fc3",
		created: "2024-12-02T18:19:07.917857Z",
		updated: "2024-12-02T18:19:07.917864Z",
		checksum:
			"sha256:61e9dbea14935ccb2cfac7eb38f01c4e878a81073806f2aec993820fa0d91eb3",
		fields: {
			block_type_slug: "webhook",
			description: "Block that enables calling webhooks.",
			properties: {
				method: {
					default: "POST",
					description: "The webhook request method. Defaults to `POST`.",
					enum: ["GET", "POST", "PUT", "PATCH", "DELETE"],
					title: "Method",
					type: "string",
				},
				url: {
					description: "The webhook URL.",
					examples: ["https://hooks.slack.com/XXX"],
					format: "password",
					title: "Webhook URL",
					type: "string",
					writeOnly: true,
				},
				headers: {
					description:
						"A dictionary of headers to send with the webhook request.",
					title: "Webhook Headers",
					type: "object",
				},
				allow_private_urls: {
					default: true,
					description:
						"Whether to allow notifications to private URLs. Defaults to True.",
					title: "Allow Private Urls",
					type: "boolean",
				},
				verify: {
					default: true,
					description:
						"Whether or not to enforce a secure connection to the webhook.",
					title: "Verify",
					type: "boolean",
				},
			},
			required: ["url"],
			secret_fields: ["url", "headers.*"],
			title: "Webhook",
			type: "object",
			block_schema_references: {},
		},
		block_type_id: "9d7a2191-4bdc-4cd5-8449-fb3b45f6588c",
		block_type: {
			id: "9d7a2191-4bdc-4cd5-8449-fb3b45f6588c",
			created: "2024-12-02T18:19:07.893315Z",
			updated: "2024-12-02T18:19:08.023000Z",
			name: "Webhook",
			slug: "webhook",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/c7247cb359eb6cf276734d4b1fbf00fb8930e89e-250x250.png",
			documentation_url:
				"https://docs.prefect.io/latest/automate/events/webhook-triggers",
			description: "Block that enables calling webhooks.",
			code_example:
				'```python\nfrom prefect.blocks.webhook import Webhook\n\nwebhook_block = Webhook.load("BLOCK_NAME")\n```',
			is_protected: true,
		},
		capabilities: [],
		version: "3.1.5",
	},
];

export const createFakeBlockSchema =
	(): components["schemas"]["BlockSchema"] => {
		return rand(BLOCK_SCHEMAS);
	};
