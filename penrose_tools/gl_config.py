# penrose_tools/gl_config.py
"""Shared OpenGL configuration — set once at startup, read by all renderers."""

import re

use_gles = False


def patch_shader(source, is_fragment=False):
    """Patch GLSL source for OpenGL ES if needed.

    Converts #version 140 -> #version 300 es with precision qualifiers.
    Also converts gl_FragColor usage to explicit output variable for GLES 300 es.
    Converts texture2D -> texture for GLES 300 es.
    No-op when running desktop GL.
    """
    if not use_gles:
        return source

    # Replace version directive
    source = re.sub(
        r'#version\s+\d+(\s+core)?',
        '#version 300 es',
        source,
        count=1
    )

    # Insert precision qualifiers after version line
    precision = "precision highp float;\nprecision highp int;\n"
    source = source.replace('#version 300 es', '#version 300 es\n' + precision, 1)

    if is_fragment:
        # Convert gl_FragColor to explicit output (GLES 300 es requires it)
        if 'gl_FragColor' in source:
            # Add output declaration after precision qualifiers
            source = source.replace(
                precision,
                precision + "out vec4 _fragColor;\n",
                1
            )
            source = source.replace('gl_FragColor', '_fragColor')

        # texture2D -> texture (GLES 300 es)
        source = source.replace('texture2D(', 'texture(')

    return source
