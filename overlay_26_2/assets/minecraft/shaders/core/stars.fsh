#version 330

#moj_import <minecraft:dynamictransforms.glsl>

out vec4 fragColor;

void vanillaMain() {
    fragColor = ColorModulator;
}

void main() {
    vanillaMain();
    fragColor = vec4(0.0);
}
