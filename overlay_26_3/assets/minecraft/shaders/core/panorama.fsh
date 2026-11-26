#version 330
#extension GL_ARB_separate_shader_objects : require

uniform samplerCube Sampler0;

layout(location = 0) in vec3 texCoord0;

layout(location = 0) out vec4 fragColor;

void vanillaMain() {
    fragColor = texture(Sampler0, texCoord0);
}

void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
