# Prefect block and worker logos

This directory contains temporary repository-hosted replacements for the Sanity
logos referenced by Prefect blocks and workers. The URL-replacement change will
point at the merged assets commit through raw GitHub URLs; registered metadata
and existing installations are not migrated by this work.

## Provenance and mapping

The current-main inventory found 54 Sanity `_logo_url` references (48 block
references and 6 worker references) and 26 distinct Sanity images. Six
Contentful-hosted logo references remain intentionally unchanged. The
requester later supplied 17 recovered Sanity originals; those files are used
for the matching assets below. The remaining assets are educated replacements
because the Sanity project returned HTTP 402 during direct recovery.

Brand artwork marked `simple-icons` comes from the version-pinned
[Simple Icons 11.0.0 icon sources](https://github.com/simple-icons/simple-icons/tree/11.0.0/icons)
and is available under CC0 1.0. Recovered originals retain their original
appearance and Sanity URL identity; their independent license and attribution
terms were not available in the recovered files. Generic artwork is original
work for this repository. The email image reuses the black outline from
Prefect's existing [integration overview artwork](https://github.com/PrefectHQ/prefect/blob/main/docs/images/integrations/email.png)
instead of using a red provider logo. The ProcessWorker image reuses Prefect's
existing generic gear artwork because a plus button did not represent process
execution. `mapping.json` records every complete Sanity source URL and its
repository asset.

The contact sheet uses color artwork. Where a recovered original was
monochrome, the corresponding Simple Icons brand color is used instead. The
GitHub mark uses a blue presentation color because its canonical mark is
monochrome; filesystem, secret, and webhook artwork uses repository-authored
blue variants.

| Sanity URL suffix | Asset | Mapped block or worker families |
| --- | --- | --- |
| `0b47a017...` | `terminal.png` | ShellOperation |
| `10424e31...` | `googlecloud.png` | GCP blocks and workers |
| `1350a147...` | `mattermost.png` | MattermostWebhook |
| `14a315b7...` | `docker.png` | DockerHost, DockerRegistryCredentials |
| `2d0b8960...` | `kubernetes.png` | Kubernetes blocks and worker |
| `356e6766...` | `process.png` | ProcessWorker |
| `3c7dff04...` | `sqlalchemy.png` | SQLAlchemy connectors |
| `3f624663...` | `smb.png` | SMB |
| `41971cf...` | `github.png` | GitHub blocks |
| `54e3fa7e...` | `microsoft-azure.png` | Azure blocks and worker |
| `5d729f73...` | `bitbucket.png` | Bitbucket blocks |
| `676cb17b...` | `minio.png` | MinIO credentials |
| `817efe00...` | `microsoft-teams.png` | MicrosoftTeamsWebhook |
| `82bc6ed1...` | `email.png` | SendgridEmail, EmailServerCredentials |
| `8bd87779...` | `twilio.png` | TwilioSMS |
| `8dbf37d1...` | `pagerduty.png` | PagerDutyWebHook |
| `9e94976c...` | `discord.png` | DiscordWebhook |
| `ad39089f...` | `filesystem.png` | LocalFileSystem |
| `bd359de0...` | `snowflake.png` | Snowflake blocks |
| `c1965ecb...` | `slack.png` | Slack blocks |
| `c6f20e55...` | `secret.png` | Secret |
| `c7247cb3...` | `webhook.png` | Webhook blocks |
| `d74b16fe...` | `aws.png` | AWS blocks and ECS worker |
| `d8b5bc62...` | `opsgenie.png` | OpsgenieWebhook |
| `dfb02cfc...` | `redis.png` | Redis blocks |
| `e86b41bc...` | `filesystem.png` | RemoteFileSystem |

`contact-sheet.png` is a full-artwork review sheet. All final PNGs are
256×256 RGBA images with transparent padding where the source artwork permits.
