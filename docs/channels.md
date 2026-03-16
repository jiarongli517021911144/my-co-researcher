# Channels

`coresearcher` exposes three channel surfaces:

- CLI
- Feishu
- QQ

The CLI works out of the box. Feishu and QQ require optional SDKs and platform credentials.

## Install Optional Dependencies

```bash
pip install -e ".[feishu]"
pip install -e ".[qq]"
```

Install both if needed:

```bash
pip install -e ".[feishu,qq]"
```

## Feishu

Required config fields:

- `channels.feishu.enabled`
- `channels.feishu.app_id`
- `channels.feishu.app_secret`

Optional fields:

- `channels.feishu.verification_token`
- `channels.feishu.encrypt_key`
- `channels.feishu.allow_from`

If the `lark-oapi` SDK is missing, the channel will remain disabled at runtime.

## QQ

Required config fields:

- `channels.qq.enabled`
- `channels.qq.app_id`
- `channels.qq.secret`

Useful optional fields:

- `channels.qq.token`
- `channels.qq.sandbox`
- `channels.qq.allow_from`

If the `qq-botpy` SDK is missing, the channel will remain disabled at runtime.

## Local Validation

```bash
python demos/channels_demo.py
python demos/qq_channel_demo.py
python -m coresearcher gateway --dry-run
```

For local development, start with CLI or web, then add platform credentials once the core runtime is stable.
