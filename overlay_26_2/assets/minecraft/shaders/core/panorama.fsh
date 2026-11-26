#version 330

uniform samplerCube Sampler0;

in vec3 texCoord0;

out vec4 fragColor;

void vanillaMain() {
    fragColor = texture(Sampler0, texCoord0);
}

void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
