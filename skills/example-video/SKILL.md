---
name: example-video
description: A general example skill for video prompts from text, keyframes, reference images, and sampled video frames.
---

# Video prompt writing example

Read `references/tasks.md` for task routing.

Write a video prompt describing how a shot changes over its requested duration. Give the subject a clear action, make camera movement physically coherent, and keep object and character identities consistent. Use timestamps only when useful and keep them within the target duration. Width and height describe the output canvas; do not mistake sampled frame count for video length.

Follow the requested language. Output only the final video prompt with these short sections: Scene and action, Camera and timing, Sound. Describe requested dialogue or sound as intended output, never as something heard in silent reference frames. If no sound is requested, keep sound suggestions brief and appropriate to the scene.

This is a general demonstration skill, not an official or model-specific MiniMax H3 guide. If the user supplies another format, follow that format.
