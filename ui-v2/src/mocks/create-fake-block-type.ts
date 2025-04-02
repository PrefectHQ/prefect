import type { components } from "@/api/prefect";
import { rand } from "@ngneat/falso";

const BLOCK_TYPES: Array<components["schemas"]["BlockType"]> = [
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
		id: "ecf55c95-35f8-47f4-b8b5-2e9793486fee",
		created: "2024-12-02T18:19:07.944913Z",
		updated: "2024-12-02T18:19:07.944915Z",
		name: "Slack Webhook",
		slug: "slack-webhook",
		logo_url:
			"https://cdn.sanity.io/images/3ugk85nk/production/c1965ecbf8704ee1ea20d77786de9a41ce1087d1-500x500.png",
		documentation_url:
			"https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations",
		description: "Enables sending notifications via a provided Slack webhook.",
		code_example:
			'Load a saved Slack webhook and send a message:\n```python\nfrom prefect.blocks.notifications import SlackWebhook\n\nslack_webhook_block = SlackWebhook.load("BLOCK_NAME")\nslack_webhook_block.notify("Hello from Prefect!")\n```',
		is_protected: false,
	},
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
	{
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
];

export const createFakeBlockType = (): components["schemas"]["BlockType"] => {
	return rand(BLOCK_TYPES);
};
