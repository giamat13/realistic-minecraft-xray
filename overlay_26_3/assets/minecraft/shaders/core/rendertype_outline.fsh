#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

layout(location = 0) in vec4 vertexColor;
layout(location = 1) in vec2 texCoord0;

layout(location = 0) out vec4 fragColor;

void vanillaMain() {
    vec4 color = texture(Sampler0, texCoord0);
    if (color.a == 0.0) {
        discard;
    }
    fragColor = vec4(ColorModulator.rgb * vertexColor.rgb, ColorModulator.a);
}

void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
