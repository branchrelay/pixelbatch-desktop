# Security Policy

## Secrets

Do not commit API keys, `.env` files, logs, exported images, CSV files with customer data, model weights, or generated output.

PixelBatch stores provider API keys through `keyring` in Windows Credential Manager when available. Non-secret preferences are stored in `%APPDATA%\PixelBatch\settings.json`.

If a key is accidentally committed or shared, revoke it at the provider immediately and create a new key. Removing the key from a later commit is not enough if it already exists in Git history.

## Local data

The application can create local logs, cache, temporary files, generated images, and downloaded rembg model weights. These files are intentionally ignored by Git and should not be published.

## Reporting

For a private repository, report security issues through the repository owner or private issue tracker. Do not post real secrets in issues, screenshots, logs, or pull requests.
