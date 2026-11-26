#version 330

#moj_import <minecraft:dynamictransforms.glsl>

out vec4 fragColor;

void vanillaMain() {
    fragColor = ColorModulator;
}

void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
