#version 330 compatibility
out vec2 uv;
out vec4 tint;
out vec3 viewPos;
out vec3 normal;
in vec4 mc_Entity;
flat out int blockId;

void main() {
    blockId = int(mc_Entity.x + 0.5);
    uv = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    tint = gl_Color;
    viewPos = (gl_ModelViewMatrix * gl_Vertex).xyz;
    normal = gl_NormalMatrix * gl_Normal;
    gl_Position = gl_ProjectionMatrix * vec4(viewPos, 1.0);
    gl_Position.z = 0.0; // one shared depth: every surface passes the depth test, so nothing hides anything
}
