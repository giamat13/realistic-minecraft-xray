#version 330 compatibility
out vec2 vUv;
out vec4 vTint;
out vec3 vViewPos;
out vec3 vNormal;
in vec4 mc_Entity;
flat out int vBlockId;
in vec4 at_midBlock; // from each corner to the middle of its block, in 1/64 of a block
flat out int vInset;

void main() {
    vBlockId = int(mc_Entity.x + 0.5);
    vInset = max(max(abs(at_midBlock.x), abs(at_midBlock.y)), abs(at_midBlock.z)) < 31.5 ? 1 : 0;
    vUv = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    vTint = gl_Color;
    vViewPos = (gl_ModelViewMatrix * gl_Vertex).xyz;
    vNormal = gl_NormalMatrix * gl_Normal;
    gl_Position = gl_ProjectionMatrix * vec4(vViewPos, 1.0);
    gl_Position.z = 0.0; // one shared depth: every surface passes the depth test, so nothing hides anything
}
