# Repository instructions

- Keep the connector, image prompt node, video prompt node and their web UI in this single plugin.
- Keep package descriptions and integration references generic; do not name unrelated custom-node packages.
- Only discover skills in this plugin's `skills` directory. Never scan global personal skill directories.
- User skills are local content. Keep them ignored. The authored basic skills and explicitly vendored `qwen-image-2-1` snapshot are bundled; keep its upstream Apache license and attribution.
- The official H3 example is installed from pinned upstream URLs with `scripts/install_h3_skill.py`. Keep its downloaded directory ignored; do not mirror the licensed H3 documents in this public repository.
- Preserve existing node IDs, sockets and saved workflow compatibility. Use ComfyUI V3 schemas for new nodes.
- Test timeout overrides without changing the original shared connector. Never publish API keys, private skills, or workflows containing real credentials.
- Run `python -m pytest tests -q` and `node tests/test_connector_ui.mjs` after relevant changes.
- Publish subsequent changes after the user confirms them or explicitly requests publication. A request to upload/push is authorization; do not ask for the same authorization again.
