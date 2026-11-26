#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:fog.glsl>


layout(location = 0) in float sphericalVertexDistance;
layout(location = 1) in float cylindricalVertexDistance;
layout(location = 2) flat in vec4 vertexColor;

layout(location = 0) out vec4 fragColor;

void vanillaMain() {
    fragColor = apply_fog(vertexColor, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}

void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
