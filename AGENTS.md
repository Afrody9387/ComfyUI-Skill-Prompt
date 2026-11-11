# Repository instructions

- Keep the connector, image prompt node, video prompt node and their web UI in this single plugin.
- Only discover skills in this plugin's `skills` directory. Never scan global personal skill directories.
- User skills are local content. Keep them ignored; only the two authored `example-image` and `example-video` skills are bundled.
- Preserve existing node IDs, sockets and saved workflow compatibility. Use ComfyUI V3 schemas for new nodes.
- Test timeout overrides without changing the original shared connector. Never publish API keys, private skills, or workflows containing real credentials.
- Run `python -m pytest tests -q` and `node tests/test_connector_ui.mjs` after relevant changes.
- Publish subsequent changes after the user confirms them or explicitly requests publication. A request to upload/push is authorization; do not ask for the same authorization again.
