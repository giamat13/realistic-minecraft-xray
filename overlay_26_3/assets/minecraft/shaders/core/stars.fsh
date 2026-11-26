#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:dynamictransforms.glsl>

layout(location = 0) out vec4 fragColor;

void vanillaMain() {
    fragColor = ColorModulator;
}

void main() {
    vanillaMain();
    fragColor = vec4(0.0);
}
