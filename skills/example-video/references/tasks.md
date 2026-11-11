# Task routing

- `t2v`: Build an evolving shot from the user's text. Reference images, if supplied, are inspiration for the written prompt.
- `i2v_first`: Begin at the first frame's state, preserve its subject, and describe what happens next.
- `i2v_first_last`: Describe a continuous path from the opening state to the ending state. Avoid hard cuts unless requested.
- `i2v_last`: Describe an opening and action that arrive at the supplied ending frame.
- `reference`: Use the supplied reference images for identity and visual cues; sampled reference video frames provide chronological motion cues. Label distinct references clearly.
- `s2v`: Use reference images to anchor the subject's identity, then describe the requested motion and setting.

Do not re-describe every static detail in a keyframe when a concise identity-preservation clause is enough. Focus on motion, spatial continuity, and changes over time.
